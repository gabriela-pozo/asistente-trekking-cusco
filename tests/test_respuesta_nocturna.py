"""Pruebas del modo nocturno (respuesta automática fuera de horario). No llaman a la API.

Correr:  python -m unittest discover tests -v
"""
import dataclasses
import os
import sys
import tempfile
import unittest
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from unittest import mock

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from ai.ejemplo import cargar_ejemplo  # noqa: E402
from core.cotizacion import cargar_tarifario  # noqa: E402
from core.respuesta_nocturna import (  # noqa: E402
    EN_ESPERA, SE_ENVIARIA, advertencias_de_control, fuera_de_horario, precio_desde, respuesta_nocturna,
)

TARIFARIO = cargar_tarifario(RAIZ / "data" / "tarifario_demo.csv")
AGENCIA = "Andes Trek Demo"
APP = str(RAIZ / "app" / "app.py")


def perfil(**cambios):
    resultado, _ = cargar_ejemplo()  # Salkantay, 2 personas, "late March", en inglés
    return resultado.perfil.model_copy(update=cambios)


def nocturna(p, advertencias=()):
    return respuesta_nocturna(p, TARIFARIO, list(advertencias), AGENCIA)


class PruebasIdiomas(unittest.TestCase):
    ESPERADO = {  # (precio, pregunta por la fecha, cuándo responde el asesor)
        "es": ("Salkantay: desde US$ 480 por persona.", "¿Qué fecha exacta tienes en mente?",
               "Un asesor te confirma disponibilidad y precio final desde las 8:00 a. m. (hora de Perú)."),
        "en": ("Salkantay: from US$ 480 per person.", "What exact date do you have in mind?",
               "An advisor will confirm availability and the final price from 8:00 a.m. (Peru time)."),
        "pt": ("Salkantay: a partir de US$ 480 por pessoa.", "Qual data exata você tem em mente?",
               "a partir das 8h (horário do Peru)."),
        "fr": ("Salkantay : à partir de US$ 480 par personne.", "Quelle date exacte envisagez-vous ?",
               "à partir de 8 h (heure du Pérou)."),
        "de": ("Salkantay: ab US$ 480 pro Person.", "An welches genaue Datum denken Sie?",
               "ab 8:00 Uhr (peruanische Zeit)."),
    }

    def test_los_cinco_idiomas(self):
        for codigo, frases in self.ESPERADO.items():
            with self.subTest(codigo):
                r = nocturna(perfil(idioma=codigo))
                self.assertTrue(r.se_enviaria_sola)
                self.assertEqual(r.idioma, codigo)
                for frase in frases:
                    self.assertIn(frase, r.mensaje)
                self.assertIn(AGENCIA, r.mensaje.splitlines()[0])  # saludo
                self.assertEqual(len([linea for linea in r.mensaje.splitlines() if "US$" in linea]), 1)

    def test_otro_idioma_responde_en_ingles(self):
        r = nocturna(perfil(idioma="ja"))
        self.assertEqual(r.idioma, "en")
        self.assertIn("from US$ 480 per person", r.mensaje)

    def test_incluye_en_una_linea_traducido(self):
        incluye = [linea for linea in nocturna(perfil()).mensaje.splitlines() if linea.startswith("Includes:")]
        self.assertEqual(len(incluye), 1)
        self.assertIn("bilingual guide", incluye[0])
        self.assertIn("Machu Picchu entrance", incluye[0])
        self.assertNotIn("Guía", incluye[0])

    def test_solo_pregunta_lo_que_falta(self):
        con_fecha = nocturna(perfil(fecha_texto="15 de marzo", datos_faltantes=[])).mensaje
        self.assertNotIn("exact date", con_fecha)
        self.assertNotIn("How many people", con_fecha)
        sin_personas = nocturna(perfil(num_personas=None)).mensaje
        self.assertIn("What exact date", sin_personas)
        self.assertIn("How many people are traveling?", sin_personas)


class PruebasPrecio(unittest.TestCase):
    def test_minimo_del_trek_para_el_grupo(self):
        self.assertEqual(precio_desde("salkantay", TARIFARIO, 2), 480)  # económico 4 días, grupo de 1–2
        self.assertEqual(precio_desde("salkantay", TARIFARIO, 6), 440)  # el mismo, con tarifa de 5 o más
        filas = TARIFARIO[TARIFARIO["ruta"] == "salkantay"]
        self.assertEqual(precio_desde("salkantay", TARIFARIO, 2), int(filas["precio_usd_pp_grupo_2"].min()))

    def test_trek_sin_precio_no_lleva_monto(self):
        self.assertIsNone(precio_desde("ausangate", TARIFARIO, 2))
        r = nocturna(perfil(treks_de_interes=["ausangate"]))
        self.assertFalse(r.se_enviaria_sola)
        self.assertEqual(r.estado, EN_ESPERA)
        self.assertNotIn("US$", r.mensaje)
        self.assertNotIn("US$", r.mensaje_completo)
        self.assertTrue(any("no tiene precio" in m for m in r.motivos))


class PruebasEstado(unittest.TestCase):
    def test_se_enviaria_sola_con_idioma_trek_y_sin_advertencias(self):
        resultado, _ = cargar_ejemplo()
        self.assertEqual(advertencias_de_control(resultado), [])  # las notas del modelo no cuentan
        r = respuesta_nocturna(resultado.perfil, TARIFARIO, advertencias_de_control(resultado), AGENCIA)
        self.assertEqual(r.estado, SE_ENVIARIA)
        self.assertEqual(r.motivos, [])

    def test_una_advertencia_bloquea_el_envio(self):
        resultado, _ = cargar_ejemplo()
        aviso = "El mensaje menciona US$ 999, que no están en la cotización."
        resultado = dataclasses.replace(resultado, advertencias=resultado.advertencias + [aviso])
        r = respuesta_nocturna(resultado.perfil, TARIFARIO, advertencias_de_control(resultado), AGENCIA)
        self.assertFalse(r.se_enviaria_sola)
        self.assertEqual(r.estado, EN_ESPERA)
        self.assertIn(aviso, " ".join(r.motivos))
        self.assertNotIn("US$", r.mensaje)  # recepción corta, sin montos
        self.assertIn("8:00 a.m. (Peru time)", r.mensaje)

    def test_sin_idioma_o_sin_trek_queda_en_espera(self):
        for p in (perfil(idioma=""), perfil(treks_de_interes=[])):
            with self.subTest(idioma=p.idioma, treks=p.treks_de_interes):
                r = nocturna(p)
                self.assertFalse(r.se_enviaria_sola)
                self.assertTrue(r.motivos)
                self.assertNotIn("US$", r.mensaje)


class PruebasHorario(unittest.TestCase):
    def test_dentro_de_horario_no_se_activa(self):
        for hora in (time(8, 0), time(12, 30), time(19, 59)):
            self.assertFalse(fuera_de_horario(datetime.combine(datetime(2026, 11, 10), hora)), hora)
        for hora in (time(0, 7), time(7, 59), time(20, 0), time(23, 30)):
            self.assertTrue(fuera_de_horario(datetime.combine(datetime(2026, 11, 10), hora)), hora)

    def test_hora_evaluada_en_lima(self):
        # 13:00 UTC = 8:00 en Lima (abierto); 03:00 UTC = 22:00 del día anterior en Lima (cerrado).
        self.assertFalse(fuera_de_horario(datetime(2026, 11, 10, 13, 0, tzinfo=timezone.utc)))
        self.assertTrue(fuera_de_horario(datetime(2026, 11, 10, 3, 0, tzinfo=timezone.utc)))
        madrid = timezone(timedelta(hours=1))  # 15:00 en Madrid = 9:00 en Lima
        self.assertFalse(fuera_de_horario(datetime(2026, 11, 10, 15, 0, tzinfo=madrid)))

    def test_horario_de_la_agencia(self):
        self.assertTrue(fuera_de_horario(datetime(2026, 11, 10, 8, 30), apertura=time(9, 0), cierre=time(18, 0)))


class PruebasPaginaNocturna(unittest.TestCase):
    def correr(self, hora, modo=True):
        from streamlit.testing.v1 import AppTest

        with tempfile.TemporaryDirectory() as carpeta, \
                mock.patch.dict(os.environ, {"GEMINI_API_KEY": "", "ABRA_REGISTRO": str(Path(carpeta) / "r.csv")}):
            app = AppTest.from_file(APP, default_timeout=30)
            app.session_state["hora_llegada"] = hora
            app.session_state["modo_nocturno"] = modo
            app.run()
            next(b for b in app.button if b.label == "Usar mensaje de ejemplo").click().run()
        self.assertFalse(app.exception)
        return " ".join(str(h.proto) for h in app.get("html"))

    def test_tarjeta_a_las_00_07(self):
        texto = self.correr(time(0, 7))
        self.assertIn("Respuesta automática fuera de horario", texto)
        self.assertIn("Se enviaría sola", texto)
        self.assertIn("Simulación: el envío automático requiere la API de WhatsApp Business (siguiente paso)", texto)
        self.assertIn("from US$ 480 per person", texto)

    def test_sin_tarjeta_dentro_de_horario_o_con_el_modo_apagado(self):
        self.assertNotIn("Respuesta automática fuera de horario", self.correr(time(10, 0)))
        self.assertNotIn("Respuesta automática fuera de horario", self.correr(time(0, 7), modo=False))


if __name__ == "__main__":
    unittest.main()
