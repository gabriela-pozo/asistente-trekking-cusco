"""Pruebas del webhook de WhatsApp (sandbox de Twilio). Sin llamadas reales: modelo y envío simulados.

La firma X-Twilio-Signature se calcula con el mismo validador de twilio-python, con un token de prueba.

Correr:  python -m unittest discover tests -v
"""
import os
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

try:  # el webhook usa requirements-server.txt (y TestClient necesita httpx)
    from fastapi.testclient import TestClient
    from twilio.request_validator import RequestValidator
except ImportError as falta:  # pragma: no cover
    raise unittest.SkipTest(f"Falta {falta.name}: pip install -r requirements-server.txt httpx")

from ai.fecha import ZONA  # noqa: E402
from ai.llm import Uso  # noqa: E402
from ai.schemas import PerfilTurista  # noqa: E402
from core.cotizacion import cargar_tarifario  # noqa: E402
from server.webhook import Recordados, crear_app  # noqa: E402

TOKEN = "token_de_prueba_no_es_real"
URL = "https://abra-webhook.onrender.com/whatsapp"
TELEFONO = "whatsapp:+15005550006"   # número de prueba (los "magic numbers" de Twilio)
TEXTO = ("Hi! We are 2 friends planning to visit Cusco in late March. Is the Salkantay trek to Machu Picchu "
         "possible in 4 or 5 days? How much would it cost per person and what is included? Thanks!")


def payload(sid="SM0123456789abcdef0123456789abcdef", body=TEXTO, de=TELEFONO):
    """Campos de un mensaje entrante de WhatsApp como los envía Twilio (form-urlencoded)."""
    return {
        "SmsMessageSid": sid, "NumMedia": "0", "ProfileName": "Viajero", "MessageType": "text",
        "SmsSid": sid, "WaId": de.removeprefix("whatsapp:+"), "SmsStatus": "received", "Body": body,
        "To": "whatsapp:+14155238886", "NumSegments": "1", "ReferralNumMedia": "0", "MessageSid": sid,
        "AccountSid": "AC00000000000000000000000000000000", "From": de, "ApiVersion": "2010-04-01",
    }


def firma(datos, url=URL, token=TOKEN):
    return RequestValidator(token).compute_signature(url, datos)


PERFIL_SALKANTAY = {"idioma": "en", "num_personas": 2, "mes_viaje": 3, "fecha_texto": "late March",
                    "treks_de_interes": ["salkantay"], "datos_faltantes": ["fecha exacta"]}


class ModeloSimulado:
    def __init__(self, perfil=PERFIL_SALKANTAY, error=None):
        self.perfil, self.error, self.llamadas = perfil, error, []

    def estructurado(self, sistema, mensaje, esquema):
        self.llamadas.append(mensaje)
        if self.error:
            raise self.error
        return esquema.model_validate(self.perfil), Uso(10, 5)


class EnviadorSimulado:
    def __init__(self):
        self.enviados = []

    def enviar(self, para, texto):
        self.enviados.append((para, texto))
        return f"SMfalso{len(self.enviados)}"


def lima(hora, minuto=0):
    return datetime(2026, 11, 10, hora, minuto, tzinfo=ZONA)


class Base(unittest.TestCase):
    hora = lima(0, 7)

    def setUp(self):
        self.entorno = mock.patch.dict(os.environ, {"URL_PUBLICA": URL, "FORZAR_MODO_NOCTURNO": "",
                                                    "AGENCIA_NOMBRE": "Andes Trek Demo"})
        self.entorno.start()
        self.modelo, self.enviador = ModeloSimulado(), EnviadorSimulado()
        self.cliente = TestClient(crear_app(llm=self.modelo, enviador=self.enviador, reloj=lambda: self.hora,
                                            auth_token=TOKEN))

    def tearDown(self):
        self.entorno.stop()

    def post(self, datos, firmar=True, cabeceras=None):
        headers = {"X-Twilio-Signature": firma(datos) if firmar else "firma-falsa"} | (cabeceras or {})
        return self.cliente.post("/whatsapp", data=datos, headers=headers)


class PruebasFirma(Base):
    def test_firma_valida_responde_twiml_vacio(self):
        r = self.post(payload())
        self.assertEqual(r.status_code, 200)
        self.assertIn("text/xml", r.headers["content-type"])
        self.assertIn("<Response></Response>", r.text)

    def test_firma_invalida_403_y_no_envia(self):
        r = self.post(payload(), firmar=False)
        self.assertEqual(r.status_code, 403)
        self.assertEqual(self.enviador.enviados, [])
        self.assertEqual(self.modelo.llamadas, [])

    def test_firma_con_otro_token_no_vale(self):
        datos = payload()
        r = self.cliente.post("/whatsapp", data=datos, headers={"X-Twilio-Signature": firma(datos, token="otro")})
        self.assertEqual(r.status_code, 403)

    def test_un_campo_cambiado_invalida_la_firma(self):
        datos = payload()
        cabecera = {"X-Twilio-Signature": firma(datos)}
        r = self.cliente.post("/whatsapp", data=dict(datos, Body="otro texto"), headers=cabecera)
        self.assertEqual(r.status_code, 403)

    def test_sin_url_publica_usa_https_del_proxy(self):
        os.environ.pop("URL_PUBLICA")
        datos = payload()
        # Render termina el https y pasa la petición por http: la firma se hizo sobre la URL https.
        r = self.cliente.post("/whatsapp", data=datos, headers={
            "X-Twilio-Signature": firma(datos, url="https://abra-webhook.onrender.com/whatsapp"),
            "X-Forwarded-Proto": "https", "Host": "abra-webhook.onrender.com"})
        self.assertEqual(r.status_code, 200)


class PruebasRespuesta(Base):
    def test_fuera_de_horario_envia_la_respuesta_segura(self):
        self.post(payload())
        self.assertEqual(len(self.enviador.enviados), 1)
        para, texto = self.enviador.enviados[0]
        self.assertEqual(para, TELEFONO)
        self.assertIn("Hi! Thanks for writing to Andes Trek Demo.", texto)
        self.assertIn("Salkantay: from US$ 480 per person.", texto)
        self.assertIn("from 8:00 a.m. (Peru time)", texto)
        self.assertEqual(self.modelo.llamadas, [TEXTO])  # el modelo recibe el mensaje tal cual

    def test_en_espanol(self):
        self.modelo.perfil = dict(PERFIL_SALKANTAY, idioma="es")
        self.post(payload(body="Hola, Salkantay para 2 en marzo, ¿precio?"))
        self.assertIn("Salkantay: desde US$ 480 por persona.", self.enviador.enviados[0][1])

    def test_trek_sin_precio_solo_acuse_sin_montos(self):
        self.modelo.perfil = dict(PERFIL_SALKANTAY, treks_de_interes=["choquequirao"])
        tarifario = cargar_tarifario(RAIZ / "data" / "tarifario_demo.csv")
        cliente = TestClient(crear_app(llm=self.modelo, enviador=self.enviador, reloj=lambda: self.hora,
                                       auth_token=TOKEN, tarifario=tarifario[tarifario["ruta"] != "choquequirao"]))
        datos = payload()
        cliente.post("/whatsapp", data=datos, headers={"X-Twilio-Signature": firma(datos)})
        self.assertEqual(len(self.enviador.enviados), 1)
        texto = self.enviador.enviados[0][1]
        self.assertNotIn("US$", texto)
        self.assertIn("We received your message", texto)

    def test_error_del_modelo_envia_acuse_en_ingles(self):
        self.modelo.error = RuntimeError("sin cuota")
        self.post(payload())
        texto = self.enviador.enviados[0][1]
        self.assertNotIn("US$", texto)
        self.assertIn("An advisor will reply from 8:00 a.m. (Peru time).", texto)

    def test_no_responde_dos_veces_al_mismo_messagesid(self):
        self.post(payload())
        self.post(payload())  # Twilio reintenta el mismo mensaje
        self.assertEqual(len(self.enviador.enviados), 1)
        self.post(payload(sid="SMffffffffffffffffffffffffffffffff"))
        self.assertEqual(len(self.enviador.enviados), 2)

    def test_ignora_mensajes_sin_texto(self):
        self.post(payload(body=""))
        self.assertEqual(self.enviador.enviados, [])


class PruebasHorario(Base):
    hora = lima(10, 0)

    def test_dentro_de_horario_no_responde(self):
        r = self.post(payload())
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.enviador.enviados, [])
        self.assertEqual(self.modelo.llamadas, [])

    def test_forzar_modo_nocturno(self):
        os.environ["FORZAR_MODO_NOCTURNO"] = "1"
        self.post(payload())
        self.assertEqual(len(self.enviador.enviados), 1)

    def test_hora_evaluada_en_lima(self):
        # 03:00 UTC del 11/11 son las 22:00 del 10/11 en Lima: fuera de horario.
        self.hora = datetime(2026, 11, 11, 3, 0, tzinfo=timezone.utc)
        self.post(payload())
        self.assertEqual(len(self.enviador.enviados), 1)


class PruebasLog(Base):
    def test_el_log_no_tiene_textos_ni_telefonos(self):
        with self.assertLogs("abra.webhook", level="INFO") as registro:
            self.post(payload())
            self.post(payload())
            self.post(payload(), firmar=False)
        todo = "\n".join(registro.output)
        self.assertIn("SM0123456789abcdef0123456789abcdef", todo)
        self.assertIn("estado=Se enviaría sola", todo)
        for privado in ("15005550006", "Salkantay trek", "friends", "US$", "Thanks for writing"):
            self.assertNotIn(privado, todo)


class PruebasSalud(Base):
    def test_salud_sin_valores_secretos(self):
        with mock.patch.dict(os.environ, {"TWILIO_ACCOUNT_SID": "ACsecreto", "TWILIO_AUTH_TOKEN": "tok",
                                          "TWILIO_WHATSAPP_FROM": "whatsapp:+14155238886"}):
            r = self.cliente.get("/salud")
        self.assertEqual(r.status_code, 200)
        datos = r.json()
        self.assertEqual((datos["estado"], datos["twilio_configurado"], datos["horario_lima"]),
                         ("ok", True, "08:00-20:00"))
        for secreto in ("ACsecreto", "tok", "14155238886"):
            self.assertNotIn(secreto, r.text)


class PruebasRecordados(unittest.TestCase):
    def test_olvida_los_mas_antiguos(self):
        r = Recordados(maximo=2)
        self.assertTrue(all(r.primera_vez(s) for s in ("a", "b", "c")))
        self.assertFalse(r.primera_vez("c"))
        self.assertTrue(r.primera_vez("a"))  # ya se había olvidado


class PruebasPerfil(unittest.TestCase):
    def test_perfil_vacio_es_valido(self):
        self.assertEqual(PerfilTurista(idioma="").treks_de_interes, [])


if __name__ == "__main__":
    unittest.main()
