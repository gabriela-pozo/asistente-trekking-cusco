"""Pruebas de los ajustes del Tablero para la presentación (textos, franjas, tablas). Sin llamadas a la API.

Correr:  python -m unittest discover tests -v
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from core.tablero import PREGUNTA_TABLERO, cargar_consultas, texto_origen  # noqa: E402

SINTETICAS = RAIZ / "data" / "consultas_sinteticas.csv"
APP = str(RAIZ / "app" / "app.py")


def abrir_tablero(carpeta):
    from streamlit.testing.v1 import AppTest

    with mock.patch.dict(os.environ, {"GEMINI_API_KEY": "", "ABRA_REGISTRO": str(Path(carpeta) / "r.csv")}):
        app = AppTest.from_file(APP, default_timeout=60)
        app.run()
        app.sidebar.radio[0].set_value("Tablero").run()
    return app


def html_de(app) -> str:
    return " ".join(str(h.proto) for h in app.get("html"))


class PruebasOrigen(unittest.TestCase):
    def test_solo_sinteticas(self):
        self.assertEqual(texto_origen(cargar_consultas(SINTETICAS)), "300 consultas sintéticas de demostración")

    def test_con_registradas_dice_cuantas(self):
        df = pd.DataFrame({"origen": ["sintética"] * 3 + ["registrada"]})
        self.assertEqual(texto_origen(df), "3 consultas sintéticas de demostración y 1 registrada en esta app")
        df = pd.DataFrame({"origen": ["sintética", "registrada", "registrada"]})
        self.assertTrue(texto_origen(df).endswith("y 2 registradas en esta app"))


class PruebasPagina(unittest.TestCase):
    def test_banda_con_la_pregunta_y_el_origen(self):
        with tempfile.TemporaryDirectory() as carpeta:
            app = abrir_tablero(carpeta)
        self.assertFalse(app.exception)
        pagina = html_de(app)
        self.assertIn(PREGUNTA_TABLERO, pagina)
        self.assertIn("300 consultas sintéticas de demostración", pagina)

    def test_definicion_de_la_tasa_de_cierre_y_sin_respuesta_de_la_agencia(self):
        with tempfile.TemporaryDirectory() as carpeta:
            app = abrir_tablero(carpeta)
        etiquetas = [m.label for m in app.metric]
        self.assertIn("Sin respuesta de la agencia", etiquetas)
        # 6 meses por defecto: 20 reservadas de 111 respondidas (las mismas cifras de metricas())
        self.assertTrue(any(c.value == "Reservadas ÷ respondidas: 20 ÷ 111" for c in app.caption))


if __name__ == "__main__":
    unittest.main()
