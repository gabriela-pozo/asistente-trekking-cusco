"""Pruebas de /whatsapp-cloud (WhatsApp Cloud API de Meta). Sin red: modelo y envío simulados."""
import hashlib
import hmac
import io
import json
import os
import sys
import unittest
import urllib.request
from pathlib import Path
from unittest import mock

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

try:
    from fastapi.testclient import TestClient
except ImportError as falta:  # pragma: no cover
    raise unittest.SkipTest(f"Falta {falta.name}: pip install -r requirements-server.txt httpx")

from server.webhook import EnviadorMeta, crear_app, trocear  # noqa: E402
from tests.test_webhook import EnviadorSimulado, ModeloSimulado, TEXTO, lima  # noqa: E402

SECRETO = "secreto_de_prueba"
VERIFICACION = "verificacion_de_prueba"
ENTORNO = {"META_VERIFY_TOKEN": VERIFICACION, "META_APP_SECRET": SECRETO, "META_ACCESS_TOKEN": "tok_falso",
           "META_PHONE_NUMBER_ID": "123456", "FORZAR_MODO_NOCTURNO": "", "AGENCIA_NOMBRE": "Andes Trek Demo"}


def mensaje(texto=TEXTO, de="51999111222", mid="wamid.AAA", tipo="text"):
    m = {"from": de, "id": mid, "timestamp": "1", "type": tipo}
    if tipo == "text":
        m["text"] = {"body": texto}
    return {"object": "whatsapp_business_account", "entry": [{"id": "1", "changes": [
        {"field": "messages", "value": {"messaging_product": "whatsapp", "messages": [m]}}]}]}


ESTADO = {"object": "whatsapp_business_account", "entry": [{"id": "1", "changes": [
    {"field": "messages", "value": {"statuses": [{"id": "wamid.X", "status": "delivered"}]}}]}]}


def cuerpo_y_firma(datos, secreto=SECRETO):
    crudo = json.dumps(datos).encode()
    return crudo, "sha256=" + hmac.new(secreto.encode(), crudo, hashlib.sha256).hexdigest()


class Base(unittest.TestCase):
    hora = lima(0, 7)
    entorno = ENTORNO

    def setUp(self):
        self.parche = mock.patch.dict(os.environ, self.entorno)
        self.parche.start()
        self.modelo, self.meta = ModeloSimulado(), EnviadorSimulado()
        self.cliente = TestClient(crear_app(llm=self.modelo, enviador=EnviadorSimulado(), enviador_meta=self.meta,
                                            reloj=lambda: self.hora))

    def tearDown(self):
        self.parche.stop()

    def post(self, datos, firma=None):
        crudo, buena = cuerpo_y_firma(datos)
        return self.cliente.post("/whatsapp-cloud", content=crudo, headers={
            "X-Hub-Signature-256": buena if firma is None else firma, "Content-Type": "application/json"})


class PruebasVerificacion(Base):
    def consulta(self, **extra):
        p = {"hub.mode": "subscribe", "hub.verify_token": VERIFICACION, "hub.challenge": "98765"} | extra
        return self.cliente.get("/whatsapp-cloud", params=p)

    def test_correcta_devuelve_el_challenge(self):
        r = self.consulta()
        self.assertEqual((r.status_code, r.text), (200, "98765"))
        self.assertIn("text/plain", r.headers["content-type"])

    def test_token_incorrecto_403(self):
        self.assertEqual(self.consulta(**{"hub.verify_token": "otro"}).status_code, 403)

    def test_modo_incorrecto_403(self):
        self.assertEqual(self.consulta(**{"hub.mode": "unsubscribe"}).status_code, 403)


class PruebasMensajes(Base):
    def test_firma_valida_y_texto_envia_al_remitente(self):
        r = self.post(mensaje())
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(self.meta.enviados), 1)
        self.assertEqual(self.meta.enviados[0][0], "51999111222")
        self.assertEqual(self.modelo.llamadas, [TEXTO])

    def test_firma_invalida_403(self):
        self.assertEqual(self.post(mensaje(), firma="sha256=00").status_code, 403)
        self.assertEqual(self.meta.enviados, [])

    def test_sin_firma_403(self):
        r = self.cliente.post("/whatsapp-cloud", content=b"{}")
        self.assertEqual(r.status_code, 403)

    def test_statuses_se_ignoran(self):
        self.assertEqual(self.post(ESTADO).status_code, 200)
        self.assertEqual(self.meta.enviados, [])

    def test_mensaje_sin_texto_se_ignora(self):
        self.assertEqual(self.post(mensaje(tipo="image")).status_code, 200)
        self.assertEqual(self.meta.enviados, [])

    def test_repetido_no_se_responde_dos_veces(self):
        self.post(mensaje())
        self.post(mensaje())
        self.assertEqual(len(self.meta.enviados), 1)

    def test_dentro_del_horario_no_responde(self):
        self.hora = lima(11)
        self.post(mensaje())
        self.assertEqual(self.meta.enviados, [])

    def test_modo_forzado_responde_de_dia(self):
        self.hora = lima(11)
        with mock.patch.dict(os.environ, {"FORZAR_MODO_NOCTURNO": "1"}):
            self.post(mensaje())
        self.assertEqual(len(self.meta.enviados), 1)

    def test_el_log_no_trae_texto_ni_numero(self):
        with self.assertLogs("abra.webhook", level="INFO") as registro:
            self.post(mensaje())
        todo = "\n".join(registro.output)
        self.assertNotIn("51999111222", todo)
        self.assertNotIn("Salkantay", todo)


class PruebasSinConfigurar(Base):
    entorno = {"META_VERIFY_TOKEN": "", "META_APP_SECRET": "", "META_ACCESS_TOKEN": "", "META_PHONE_NUMBER_ID": ""}

    def test_503_en_get_y_post(self):
        self.assertEqual(self.cliente.get("/whatsapp-cloud", params={"hub.mode": "subscribe"}).status_code, 503)
        r = self.cliente.post("/whatsapp-cloud", content=b"{}")
        self.assertEqual(r.status_code, 503)
        self.assertIn("META_APP_SECRET", r.text)

    def test_salud_meta_false(self):
        self.assertIs(self.cliente.get("/salud").json()["meta_configurado"], False)


class PruebasSalud(Base):
    def test_salud_meta_true(self):
        self.assertIs(self.cliente.get("/salud").json()["meta_configurado"], True)


class RespuestaFalsa(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class PruebasEnvio(unittest.TestCase):
    def test_pedido_a_la_api_de_graph(self):
        pedidos = []

        def abrir(pedido):
            pedidos.append(pedido)
            return RespuestaFalsa(b'{"messages":[{"id":"wamid.OUT"}]}')

        r = EnviadorMeta("555", "tok", abrir=abrir).enviar("51999", "hola")
        self.assertEqual(r, "wamid.OUT")
        p = pedidos[0]
        self.assertEqual(p.full_url, "https://graph.facebook.com/v21.0/555/messages")
        self.assertEqual(p.get_header("Authorization"), "Bearer tok")
        self.assertEqual(json.loads(p.data), {"messaging_product": "whatsapp", "to": "51999", "type": "text",
                                              "text": {"body": "hola"}})

    def test_error_de_la_api_no_rompe_el_servidor(self):
        def abrir(pedido):
            raise urllib.error.URLError("sin red")

        with mock.patch.dict(os.environ, ENTORNO):
            app = crear_app(llm=ModeloSimulado(), enviador_meta=EnviadorMeta("1", "t", abrir=abrir),
                            reloj=lambda: lima(0, 7))
            crudo, firma = cuerpo_y_firma(mensaje())
            r = TestClient(app).post("/whatsapp-cloud", content=crudo, headers={"X-Hub-Signature-256": firma})
        self.assertEqual(r.status_code, 200)

    def test_trocear_por_parrafos(self):
        texto = "\n\n".join(["a" * 1500] * 4)
        trozos = trocear(texto)
        self.assertTrue(all(len(t) <= 4000 for t in trozos))
        self.assertEqual(len(trozos), 2)
        self.assertEqual("\n\n".join(trozos), texto)
        self.assertEqual([len(t) for t in trocear("b" * 9000)], [4000, 4000, 1000])
