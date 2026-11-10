"""Pruebas del flujo principal con un modelo SIMULADO: no llaman a ninguna API ni necesitan clave.

Correr:  python -m unittest discover tests -v
"""
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

from pydantic import ValidationError

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from ai import prompts  # noqa: E402
from ai.knowledge import BaseConocimiento  # noqa: E402
from ai.llm import GeminiLLM, Uso, con_reintentos, crear_llm  # noqa: E402
from ai.pipeline import contar_palabras, precios_en_texto, procesar_consulta  # noqa: E402
from ai.schemas import BorradorRespuesta, PerfilTurista  # noqa: E402
from core.cotizacion import cargar_extras, cargar_tarifario  # noqa: E402

BASE = BaseConocimiento(RAIZ / "data" / "knowledge")
TARIFARIO = cargar_tarifario(RAIZ / "data" / "tarifario_demo.csv")
EXTRAS = cargar_extras(RAIZ / "data" / "extras_demo.csv")

# La consulta de la prueba de cliente misterioso.
CONSULTA = ("Hi! We are 2 friends planning to visit Cusco in late March. Is the Salkantay trek to Machu Picchu "
            "possible in 4 or 5 days? How much would it cost per person and what is included? Thanks!")

PERFIL_SALKANTAY = {
    "idioma": "en", "num_personas": 2, "mes_viaje": 3, "fecha_texto": "late March", "dias_disponibles": 5,
    "treks_de_interes": ["salkantay"], "temas_consulta": ["precio", "qué incluye"],
    "datos_faltantes": ["fecha exacta", "nivel de servicio"],
}

# Lo que respondería un buen modelo con la cotización de este caso (Salkantay 4 días estándar, 2 personas).
MENSAJE_BUENO = (
    "Hi! Yes, the Salkantay trek is possible in late March. Our standard 4-day option is US$ 600 per person, "
    "US$ 1,200 in total for 2. Included: bilingual guide, transport, meals on the trek, Machu Picchu entrance, "
    "train back to Ollantaytambo, double tent. Not included: sleeping bag (rental), travel insurance, tips, "
    "Huayna Picchu. March is rainy season, so bring rain gear. Deposit US$ 600 (50 %) to book; balance US$ 600 "
    "up to 30 days before the trek. What exact date do you have in mind? Would you prefer economy, standard "
    "or premium service?"
)


def borrador(mensaje=MENSAJE_BUENO, idioma="en", preguntas=("What exact date do you have in mind?",)):
    return {"idioma": idioma, "mensaje_para_cliente": mensaje, "preguntas_al_turista": list(preguntas),
            "advertencias_para_agencia": []}


class LLMSimulado:
    """Hace de modelo: devuelve respuestas fijas según el esquema pedido y guarda cada llamada."""

    def __init__(self, perfil: dict, borrador: dict):
        self.respuestas = {PerfilTurista: perfil, BorradorRespuesta: borrador}
        self.llamadas = []

    def estructurado(self, sistema, mensaje, esquema):
        self.llamadas.append({"sistema": sistema, "mensaje": mensaje, "esquema": esquema})
        return esquema.model_validate(self.respuestas[esquema]), Uso(100, 50)


def correr(perfil=PERFIL_SALKANTAY, respuesta=None, consulta=CONSULTA):
    llm = LLMSimulado(perfil, respuesta or borrador())
    return procesar_consulta(consulta, llm, BASE, TARIFARIO, EXTRAS), llm


class PruebasFlujo(unittest.TestCase):
    def test_flujo_completo_sin_advertencias(self):
        r, llm = correr()
        self.assertEqual([c["esquema"] for c in llm.llamadas], [PerfilTurista, BorradorRespuesta])
        self.assertEqual((r.opciones[0].trek_id, r.opciones[0].precio_pp, r.opciones[0].total),
                         ("salkantay_4d", 600, 1200))
        self.assertEqual(r.precios_no_autorizados, [])
        self.assertEqual(r.advertencias, [])
        self.assertEqual(r.uso, Uso(200, 100))

    def test_borrador_no_pasa_de_150_palabras(self):
        r, _ = correr()
        self.assertLess(contar_palabras(r.borrador.mensaje_para_cliente), prompts.LIMITE_PALABRAS)

    def test_el_modelo_recibe_cotizacion_conocimiento_y_aviso(self):
        r, llm = correr()
        mensaje = llm.llamadas[1]["mensaje"]
        self.assertIn("US$ 600 por persona", mensaje)          # precio calculado por el código
        self.assertIn("Depósito US$ 600", mensaje)             # depósito y saldo, también del código
        self.assertIn("[condiciones_reserva ·", mensaje)       # siempre entran las condiciones de reserva
        self.assertIn("[salkantay ·", mensaje)                 # y el trek pedido
        self.assertIn("temporada de lluvias", r.aviso)         # marzo: aviso de lluvias
        self.assertIn("FECHA PEDIDA POSIBLE: Sí", mensaje)

    def test_la_consulta_va_al_modelo_tal_cual(self):
        _, llm = correr()
        self.assertEqual(llm.llamadas[0]["mensaje"], CONSULTA)
        self.assertEqual(llm.llamadas[0]["sistema"], prompts.SISTEMA_EXTRAER)


class PruebasControles(unittest.TestCase):
    def test_detecta_precio_inventado(self):
        r, _ = correr(respuesta=borrador(MENSAJE_BUENO.replace("US$ 600 per person", "US$ 550 per person")))
        self.assertEqual(r.precios_no_autorizados, [550])
        self.assertTrue(any("550" in a for a in r.advertencias))

    def test_detecta_mensaje_largo(self):
        largo = MENSAJE_BUENO + " We also offer many other treks in the region." * 10
        self.assertGreaterEqual(contar_palabras(largo), prompts.LIMITE_PALABRAS)
        r, _ = correr(respuesta=borrador(largo))
        self.assertTrue(any("palabras" in a for a in r.advertencias))

    def test_detecta_idioma_distinto(self):
        r, _ = correr(respuesta=borrador(idioma="es"))
        self.assertTrue(any("'es'" in a and "'en'" in a for a in r.advertencias))

    def test_detecta_mensaje_sin_precio(self):
        r, _ = correr(respuesta=borrador("Hi! Please check the price in the attached PDF. Which date?"))
        self.assertTrue(any("no dice el precio" in a for a in r.advertencias))

    def test_detecta_mensaje_sin_preguntas(self):
        r, _ = correr(respuesta=borrador(preguntas=()))
        self.assertTrue(any("pregunta" in a for a in r.advertencias))

    def test_detecta_linea_de_deposito_sin_traducir(self):
        mensaje = MENSAJE_BUENO.replace("Deposit US$ 600 (50 %) to book; balance US$ 600 up to 30 days before the trek.",
                                        "Depósito US$ 600 (50 % del total) para reservar; saldo US$ 600 hasta 30 días antes del trek.")
        r, _ = correr(respuesta=borrador(mensaje))
        self.assertTrue(any("español" in a for a in r.advertencias))

    def test_detecta_lista_sin_traducir(self):
        perfil = dict(PERFIL_SALKANTAY, idioma="pt")
        mensaje = "Olá! US$ 600 por pessoa, US$ 1200 no total. Inclui: guía bilingüe. No incluye: Bolsa de dormir. Qual data?"
        r, _ = correr(perfil=perfil, respuesta=borrador(mensaje, idioma="pt"))
        self.assertTrue(any("español" in a for a in r.advertencias))

    def test_portugues_para_reservar_no_es_espanol(self):
        perfil = dict(PERFIL_SALKANTAY, idioma="pt")
        mensaje = "Olá! O Salkantay custa US$ 600 por pessoa, US$ 1200 no total. Depósito US$ 600 para reservar. Qual data?"
        r, _ = correr(perfil=perfil, respuesta=borrador(mensaje, idioma="pt"))
        self.assertEqual(r.advertencias, [])

    def test_detecta_promesa_de_cupo(self):
        for frase in ("Temos vagas para o Natal!", "Good news, we have availability for Christmas!", "¡Hay cupo!"):
            r, _ = correr(respuesta=borrador(frase + " " + MENSAJE_BUENO))
            self.assertTrue(any("cupo" in a for a in r.advertencias), frase)

    def test_maximo_dos_opciones(self):
        r, _ = correr()
        self.assertEqual(len(r.opciones), 2)

    def test_en_espanol_no_avisa_traduccion(self):
        perfil = dict(PERFIL_SALKANTAY, idioma="es")
        mensaje = "¡Hola! El Salkantay de 4 días cuesta US$ 600 por persona, US$ 1200 en total. ¿Qué fecha exacta?"
        r, _ = correr(perfil=perfil, respuesta=borrador(mensaje, idioma="es"))
        self.assertEqual(r.advertencias, [])

    def test_precios_en_texto(self):
        self.assertEqual(precios_en_texto("US$ 600, $1,200, USD 680, 1.360 USD y 75 dollars; 4 días, 50 %"),
                         [600, 1200, 680, 1360, 75])


class PruebasCasos(unittest.TestCase):
    def test_camino_inca_en_febrero_ofrece_alternativa_y_pregunta(self):
        perfil = dict(PERFIL_SALKANTAY, treks_de_interes=["camino_inca"], mes_viaje=2, fecha_texto="February")
        r, llm = correr(perfil=perfil, respuesta=borrador("Hi! The Inca Trail is closed in February. "
                                                          "Salkantay is US$ 600 per person, US$ 1,200 total. "
                                                          "Would it work for you?"))
        self.assertTrue(r.opciones and all(o.es_alternativa for o in r.opciones))
        self.assertIn("FECHA PEDIDA POSIBLE: No", llm.llamadas[1]["mensaje"])

    def test_camino_inca_avisa_permisos_y_permite_parte_no_reembolsable(self):
        perfil = dict(PERFIL_SALKANTAY, treks_de_interes=["camino_inca"], mes_viaje=6, dias_disponibles=4)
        mensaje = ("Hi! The classic Inca Trail is US$ 840 per person, US$ 1,680 total. Deposit US$ 840; "
                   "US$ 200 per person is non-refundable. Which exact date?")
        r, _ = correr(perfil=perfil, respuesta=borrador(mensaje))
        self.assertIn("permisos del Camino Inca", r.aviso)
        self.assertEqual(r.precios_no_autorizados, [])


class PruebasPresupuesto(unittest.TestCase):
    PERFIL = dict(PERFIL_SALKANTAY, treks_de_interes=["camino_inca"], mes_viaje=8, num_personas=1,
                  dias_disponibles=None, nivel_preferido="economico", presupuesto_usd_pp=300)

    def test_presupuesto_bajo_genera_nota_y_se_puede_citar(self):
        mensaje = ("Hi! Unfortunately US$ 300 is not enough for the Inca Trail: our cheapest option is US$ 670 "
                   "per person. Which date?")
        r, llm = correr(perfil=self.PERFIL, respuesta=borrador(mensaje))
        self.assertIn("NOTA DE PRESUPUESTO: El presupuesto del turista (US$ 300", llm.llamadas[1]["mensaje"])
        self.assertEqual(r.precios_no_autorizados, [])  # 300 es el presupuesto del turista, no un precio inventado

    def test_presupuesto_suficiente_sin_nota(self):
        r, llm = correr(perfil=dict(self.PERFIL, presupuesto_usd_pp=2000))
        self.assertIn("NOTA DE PRESUPUESTO: ninguna", llm.llamadas[1]["mensaje"])


class PruebasEsquemas(unittest.TestCase):
    def test_rechaza_trek_inexistente(self):
        with self.assertRaises(ValidationError):
            PerfilTurista.model_validate(dict(PERFIL_SALKANTAY, treks_de_interes=["everest"]))

    def test_rechaza_mes_fuera_de_rango(self):
        with self.assertRaises(ValidationError):
            PerfilTurista.model_validate(dict(PERFIL_SALKANTAY, mes_viaje=13))

    def test_lo_que_no_dice_queda_vacio(self):
        perfil = PerfilTurista.model_validate({"idioma": "en"})
        self.assertIsNone(perfil.num_personas)
        self.assertEqual(perfil.treks_de_interes, [])

    def test_maximo_dos_preguntas(self):
        with self.assertRaises(ValidationError):
            BorradorRespuesta.model_validate(borrador(preguntas=("a?", "b?", "c?")))


class PruebasReglas(unittest.TestCase):
    def test_reglas_del_cliente_misterioso_estan_en_el_prompt(self):
        texto = prompts.SISTEMA_RESPONDER
        for frase in ("idioma del turista", "precio por persona y el total", "PDF", "qué incluye y qué no incluye",
                      "AVISO CLAVE", "depósito y el saldo en una sola línea", "Nunca cambies la fecha sin preguntar",
                      "1 o 2 preguntas", "menos de 150 palabras", "la agencia lo confirmará"):
            self.assertIn(frase, texto)


class ErrorSimulado(Exception):
    def __init__(self, code):
        self.code = code


class PruebasLLM(unittest.TestCase):
    def test_reintenta_ante_429(self):
        intentos, esperas = [], []

        def llamada():
            intentos.append(1)
            if len(intentos) < 3:
                raise ErrorSimulado(429)
            return "ok"

        resultado = con_reintentos(llamada, lambda e: getattr(e, "code", None) == 429, dormir=esperas.append)
        self.assertEqual(resultado, "ok")
        self.assertEqual(len(intentos), 3)
        self.assertEqual(len(esperas), 2)
        self.assertLess(esperas[0], esperas[1])  # cada espera es más larga

    def test_no_reintenta_otros_errores(self):
        intentos = []

        def llamada():
            intentos.append(1)
            raise ErrorSimulado(400)

        with self.assertRaises(ErrorSimulado):
            con_reintentos(llamada, lambda e: e.code == 429, dormir=lambda s: None)
        self.assertEqual(len(intentos), 1)

    def test_se_rinde_despues_de_varios_429(self):
        with self.assertRaises(ErrorSimulado):
            con_reintentos(lambda: (_ for _ in ()).throw(ErrorSimulado(429)), lambda e: e.code == 429,
                           intentos=3, dormir=lambda s: None)

    def test_gemini_reconoce_el_429(self):
        from google.genai import errors

        limite = errors.ClientError(429, {"error": {"code": 429, "message": "cuota", "status": "RESOURCE_EXHAUSTED"}})
        invalido = errors.ClientError(400, {"error": {"code": 400, "message": "mal", "status": "INVALID_ARGUMENT"}})
        self.assertTrue(GeminiLLM.es_reintentable(limite))
        self.assertFalse(GeminiLLM.es_reintentable(invalido))

    def test_gemini_no_reintenta_la_cuota_diaria(self):
        from google.genai import errors

        diario = errors.ClientError(429, {"error": {"code": 429, "message": "cuota", "status": "RESOURCE_EXHAUSTED",
                                                    "details": [{"violations": [{"quotaId": "GenerateRequestsPerDayPerProjectPerModel-FreeTier"}]}]}})
        self.assertTrue(GeminiLLM.es_limite_diario(diario))
        self.assertFalse(GeminiLLM.es_reintentable(diario))

    def test_proveedor_por_defecto_es_gemini_y_pide_clave(self):
        with mock.patch.dict(os.environ, {"LLM_PROVIDER": "", "GEMINI_API_KEY": ""}):
            with self.assertRaisesRegex(RuntimeError, "GEMINI_API_KEY"):
                crear_llm()

    def test_proveedor_claude_pide_su_clave(self):
        with mock.patch.dict(os.environ, {"LLM_PROVIDER": "claude", "ANTHROPIC_API_KEY": ""}):
            with self.assertRaisesRegex(RuntimeError, "ANTHROPIC_API_KEY"):
                crear_llm()

    def test_proveedor_desconocido(self):
        with self.assertRaises(ValueError):
            crear_llm("otro")


if __name__ == "__main__":
    unittest.main()
