"""Pruebas de la app (sin navegador ni API) y del enlace de WhatsApp.

Correr:  python -m unittest discover tests -v
"""
import os
import sys
import unittest
from pathlib import Path
from unittest import mock
from urllib.parse import parse_qs, urlparse

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from core.whatsapp import enlace_whatsapp, solo_digitos  # noqa: E402

APP = str(RAIZ / "app" / "app.py")


class PruebasWhatsApp(unittest.TestCase):
    def test_numero_solo_digitos(self):
        self.assertEqual(solo_digitos("+1 (555) 123-4567"), "15551234567")
        self.assertEqual(solo_digitos(None), "")

    def test_enlace_con_numero(self):
        enlace = enlace_whatsapp("Hola", "+51 984 123 456")
        self.assertTrue(enlace.startswith("https://wa.me/51984123456?text="))

    def test_enlace_sin_numero(self):
        self.assertTrue(enlace_whatsapp("Hola").startswith("https://wa.me/?text="))

    def test_el_mensaje_se_recupera_intacto(self):
        texto = "Hi! US$ 600 per person & total US$ 1,200.\nIncluded: guía, Machu Picchu?"
        enlace = enlace_whatsapp(texto)
        self.assertNotIn(" ", enlace)
        self.assertNotIn("\n", enlace)
        self.assertEqual(parse_qs(urlparse(enlace).query)["text"][0], texto)


class PruebasApp(unittest.TestCase):
    def correr(self, **entorno):
        from streamlit.testing.v1 import AppTest

        with mock.patch.dict(os.environ, entorno):
            app = AppTest.from_file(APP, default_timeout=30)
            app.run()
        return app

    def test_sin_clave_muestra_aviso_y_no_error(self):
        app = self.correr(LLM_PROVIDER="gemini", GEMINI_API_KEY="")
        self.assertFalse(app.exception)
        self.assertTrue(any("GEMINI_API_KEY" in w.value for w in app.warning))
        boton = next(b for b in app.button if b.label == "Preparar respuesta")
        self.assertTrue(boton.disabled)

    def test_boton_de_ejemplo(self):
        from streamlit.testing.v1 import AppTest

        with mock.patch.dict(os.environ, {"GEMINI_API_KEY": ""}):
            app = AppTest.from_file(APP, default_timeout=30)
            app.run()
            with mock.patch("ai.llm.crear_llm", side_effect=AssertionError("no debe llamar a la API")):
                next(b for b in app.button if b.label == "Usar mensaje de ejemplo").click().run()
        self.assertFalse(app.exception)
        self.assertIn("Salkantay", app.text_area(key="consulta").value)
        self.assertIn("US$ 600", app.text_area(key="borrador").value)          # el borrador guardado
        self.assertTrue(any("No se llamó a la API" in i.value for i in app.info))
        self.assertTrue(any("Respondió: gemini-3.5-flash" in c.value for c in app.caption))

    def test_respondio_va_justo_encima_del_boton_de_whatsapp(self):
        from streamlit.testing.v1 import AppTest

        with mock.patch.dict(os.environ, {"GEMINI_API_KEY": ""}):
            app = AppTest.from_file(APP, default_timeout=30)
            app.run()
            next(b for b in app.button if b.label == "Usar mensaje de ejemplo").click().run()
        self.assertFalse(app.exception)
        # Elementos de la página principal en orden de aparición.
        elementos = list(app.main)
        boton = next(i for i, e in enumerate(elementos)
                     if e.type == "link_button" or getattr(e.proto, "label", "") == "Abrir en WhatsApp")
        anterior = elementos[boton - 1]
        self.assertEqual(anterior.type, "caption")
        self.assertTrue(anterior.value.startswith("Respondió: gemini-3.5-flash · Tokens usados"))

    def test_clave_no_ascii_da_mensaje_de_clave(self):
        from streamlit.testing.v1 import AppTest

        with mock.patch.dict(os.environ, {"LLM_PROVIDER": "gemini", "GEMINI_API_KEY": "clave-con-ñ"}), \
                mock.patch("google.genai.Client", side_effect=AssertionError("no debe llamar a la API")):
            app = AppTest.from_file(APP, default_timeout=30)
            app.run()
            app.text_area(key="consulta").set_value("Hi! Salkantay in March for 2?").run()
            next(b for b in app.button if b.label == "Preparar respuesta").click().run()
        self.assertFalse(app.exception)
        errores = [e.value for e in app.error]
        self.assertIn("La clave de la API no es válida: revisa GEMINI_API_KEY en .env o en los Secrets de Streamlit",
                      errores)
        self.assertFalse(any("Intenta de nuevo" in e for e in errores))

    def test_pagina_mi_agencia_muestra_tarifario(self):
        from streamlit.testing.v1 import AppTest

        with mock.patch.dict(os.environ, {"GEMINI_API_KEY": ""}):
            app = AppTest.from_file(APP, default_timeout=30)
            app.run()
            app.sidebar.radio[0].set_value("Mi agencia").run()
        self.assertFalse(app.exception)
        self.assertEqual(app.header[0].value, "Mi agencia")
        self.assertEqual(len(app.session_state["tarifario"]), 9)


if __name__ == "__main__":
    unittest.main()
