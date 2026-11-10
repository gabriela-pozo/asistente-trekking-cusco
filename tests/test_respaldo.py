"""Pruebas de la cadena de respaldo: modelo principal -> modelo de respaldo -> ejemplo guardado.

Usan un cliente de Gemini SIMULADO que falla con 429 o 503: no llaman a la API.

Correr:  python -m unittest discover tests -v
"""
import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

from google.genai import errors

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from ai.ejemplo import RUTA_EJEMPLO, cargar_ejemplo, resultado_a_dict, responder_con_respaldo  # noqa: E402
from ai.knowledge import BaseConocimiento  # noqa: E402
from ai.llm import INTENTOS, ClaveInvalidaError, GeminiLLM, ModelosNoDisponiblesError  # noqa: E402
from ai.pipeline import contar_palabras  # noqa: E402
from ai.schemas import BorradorRespuesta, PerfilTurista  # noqa: E402
from core.cotizacion import cargar_extras, cargar_tarifario  # noqa: E402

BASE = BaseConocimiento(RAIZ / "data" / "knowledge")
TARIFARIO = cargar_tarifario(RAIZ / "data" / "tarifario_demo.csv")
EXTRAS = cargar_extras(RAIZ / "data" / "extras_demo.csv")
PRINCIPAL, RESPALDO = "gemini-3.5-flash", "gemini-3.5-flash-lite"
CONSULTA = "Hi! 2 friends, Salkantay in late March, 4 or 5 days. Price per person and what is included?"

SIN_CUOTA = errors.ClientError(429, {"error": {
    "code": 429, "message": "Quota exceeded", "status": "RESOURCE_EXHAUSTED",
    "details": [{"violations": [{"quotaId": "GenerateRequestsPerDayPerProjectPerModel-FreeTier"}]}]}})
SATURADO = errors.ServerError(503, {"error": {"code": 503, "message": "high demand", "status": "UNAVAILABLE"}})
CLAVE_INVALIDA = errors.ClientError(400, {"error": {"code": 400, "message": "API key not valid", "status": "INVALID_ARGUMENT"}})

PERFIL = {"idioma": "en", "num_personas": 2, "mes_viaje": 3, "dias_disponibles": 5, "treks_de_interes": ["salkantay"],
          "datos_faltantes": ["fecha exacta"]}
BORRADOR = {"idioma": "en", "preguntas_al_turista": ["Which date?"], "advertencias_para_agencia": [],
            "mensaje_para_cliente": "Hi! Salkantay 4 days: US$ 600 per person, US$ 1200 total. "
                                    "Deposit US$ 600, balance US$ 600. Which date?"}


class ClienteSimulado:
    """Imita genai.Client: cada modelo falla con un error o responde según el esquema pedido."""

    def __init__(self, comportamiento: dict):
        self.comportamiento = comportamiento  # modelo -> excepción, o None si responde bien
        self.llamadas: list[str] = []
        self.models = SimpleNamespace(generate_content=self.generate_content)

    def generate_content(self, model, contents, config):
        self.llamadas.append(model)
        error = self.comportamiento.get(model)
        if error is not None:
            raise error
        datos = PERFIL if config.response_schema is PerfilTurista else BORRADOR
        return SimpleNamespace(parsed=None, text=json.dumps(datos),
                               usage_metadata=SimpleNamespace(prompt_token_count=100, candidates_token_count=20))


def gemini(comportamiento: dict, respaldo: str = RESPALDO) -> tuple[GeminiLLM, ClienteSimulado]:
    cliente = ClienteSimulado(comportamiento)
    return GeminiLLM(modelo=PRINCIPAL, respaldo=respaldo, cliente=cliente, dormir=lambda s: None), cliente


class PruebasCadena(unittest.TestCase):
    def test_principal_responde(self):
        llm, cliente = gemini({})
        _, uso = llm.estructurado("s", "m", PerfilTurista)
        self.assertEqual(uso.modelos, [PRINCIPAL])
        self.assertEqual(cliente.llamadas, [PRINCIPAL])

    def test_sin_cuota_pasa_al_respaldo(self):
        llm, cliente = gemini({PRINCIPAL: SIN_CUOTA})
        perfil, uso = llm.estructurado("s", "m", PerfilTurista)
        self.assertEqual(perfil.idioma, "en")
        self.assertEqual(uso.modelos, [RESPALDO])
        self.assertEqual(cliente.llamadas, [PRINCIPAL, RESPALDO])  # el 429 diario no se reintenta

    def test_principal_sin_cuota_no_se_vuelve_a_intentar(self):
        llm, cliente = gemini({PRINCIPAL: SIN_CUOTA})
        llm.estructurado("s", "m", PerfilTurista)
        llm.estructurado("s", "m", BorradorRespuesta)
        self.assertEqual(cliente.llamadas, [PRINCIPAL, RESPALDO, RESPALDO])

    def test_saturado_reintenta_y_luego_pasa_al_respaldo(self):
        llm, cliente = gemini({PRINCIPAL: SATURADO})
        _, uso = llm.estructurado("s", "m", PerfilTurista)
        self.assertEqual(cliente.llamadas, [PRINCIPAL] * INTENTOS + [RESPALDO])
        self.assertEqual(uso.modelos, [RESPALDO])

    def test_los_dos_sin_cuota(self):
        llm, _ = gemini({PRINCIPAL: SIN_CUOTA, RESPALDO: SIN_CUOTA})
        with self.assertRaisesRegex(ModelosNoDisponiblesError, "sin cuota diaria"):
            llm.estructurado("s", "m", PerfilTurista)

    def test_otro_error_no_usa_el_respaldo(self):
        error_esquema = errors.ClientError(400, {"error": {"code": 400, "message": "Invalid JSON schema",
                                                           "status": "INVALID_ARGUMENT"}})
        llm, cliente = gemini({PRINCIPAL: error_esquema})
        with self.assertRaises(errors.ClientError):
            llm.estructurado("s", "m", PerfilTurista)
        self.assertEqual(cliente.llamadas, [PRINCIPAL])


class PruebasClaveInvalida(unittest.TestCase):
    MENSAJE = "La clave de la API no es válida: revisa GEMINI_API_KEY en .env o en los Secrets de Streamlit"

    def test_400_por_clave_da_mensaje_claro_sin_respaldo(self):
        llm, cliente = gemini({PRINCIPAL: CLAVE_INVALIDA})
        with self.assertRaises(ClaveInvalidaError) as ctx:
            llm.estructurado("s", "m", PerfilTurista)
        self.assertEqual(str(ctx.exception), self.MENSAJE)
        self.assertEqual(cliente.llamadas, [PRINCIPAL])  # ni reintentos ni respaldo

    def test_401_y_403(self):
        for codigo, estado in ((401, "UNAUTHENTICATED"), (403, "PERMISSION_DENIED")):
            with self.subTest(codigo=codigo):
                error = errors.ClientError(codigo, {"error": {"code": codigo, "message": "denied", "status": estado}})
                llm, cliente = gemini({PRINCIPAL: error})
                with self.assertRaisesRegex(ClaveInvalidaError, "GEMINI_API_KEY"):
                    llm.estructurado("s", "m", PerfilTurista)
                self.assertEqual(cliente.llamadas, [PRINCIPAL])

    def test_clave_con_caracteres_no_ascii(self):
        # Se detecta al crear el cliente, antes de cualquier llamada a la API.
        with self.assertRaises(ClaveInvalidaError) as ctx:
            GeminiLLM(api_key="clave-copiada-con-“comillas”-y-ñ")
        self.assertEqual(str(ctx.exception), self.MENSAJE)

    def test_la_cadena_de_respaldo_no_esconde_la_clave_invalida(self):
        llm, _ = gemini({PRINCIPAL: CLAVE_INVALIDA})
        with self.assertRaises(ClaveInvalidaError):
            responder_con_respaldo(CONSULTA, llm, BASE, TARIFARIO, EXTRAS)

    def test_sin_respaldo_configurado(self):
        llm, _ = gemini({PRINCIPAL: SIN_CUOTA}, respaldo="")
        with self.assertRaises(ModelosNoDisponiblesError):
            llm.estructurado("s", "m", PerfilTurista)


class PruebasFlujoConRespaldo(unittest.TestCase):
    def test_429_en_el_principal_responde_el_respaldo(self):
        llm, _ = gemini({PRINCIPAL: SIN_CUOTA})
        resultado, es_ejemplo = responder_con_respaldo(CONSULTA, llm, BASE, TARIFARIO, EXTRAS)
        self.assertFalse(es_ejemplo)
        self.assertEqual(resultado.uso.modelos_que_respondieron(), RESPALDO)
        self.assertEqual(resultado.precios_no_autorizados, [])

    def test_429_en_los_dos_muestra_el_ejemplo_guardado(self):
        llm, cliente = gemini({PRINCIPAL: SIN_CUOTA, RESPALDO: SIN_CUOTA})
        resultado, es_ejemplo = responder_con_respaldo(CONSULTA, llm, BASE, TARIFARIO, EXTRAS)
        self.assertTrue(es_ejemplo)
        self.assertEqual(cliente.llamadas, [PRINCIPAL, RESPALDO])
        guardado, _ = cargar_ejemplo()
        self.assertEqual(resultado.borrador, guardado.borrador)


class PruebasEjemploGuardado(unittest.TestCase):
    def setUp(self):
        self.resultado, self.datos = cargar_ejemplo()

    def test_se_carga_igual_que_se_guardo(self):
        otra_vez = resultado_a_dict(self.resultado, self.datos["consulta"], self.datos["fecha"])
        self.assertEqual(json.loads(json.dumps(otra_vez)), json.loads(RUTA_EJEMPLO.read_text(encoding="utf-8")))

    def test_viene_del_modelo_principal_y_pasa_el_control(self):
        self.assertEqual(self.resultado.uso.modelos_que_respondieron(), PRINCIPAL)
        self.assertEqual(self.resultado.precios_no_autorizados, [])
        self.assertLess(contar_palabras(self.resultado.borrador.mensaje_para_cliente), 150)
        self.assertEqual(self.resultado.borrador.idioma, self.resultado.perfil.idioma)

    def test_sin_datos_personales(self):
        texto = RUTA_EJEMPLO.read_text(encoding="utf-8")
        self.assertNotRegex(texto, r"[\w.+-]+@[\w-]+\.\w+")         # correos
        self.assertNotRegex(texto, r"\+\d[\d\s()-]{7,}")            # teléfonos
        self.assertNotIn("AIza", texto)                             # claves de Google


if __name__ == "__main__":
    unittest.main()
