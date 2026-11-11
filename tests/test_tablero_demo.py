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

from core.tablero import (  # noqa: E402
    PERIODOS, PREGUNTA_TABLERO, cargar_consultas, cierre_por_trek, embudo, filtrar, metricas, periodo,
    por_mes_y_estado, texto_origen,
)

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


class PruebasCuadre(unittest.TestCase):
    """KPIs, embudo, por trek y mes × estado cuadran entre sí con los mismos filtros (datos sintéticos)."""

    def test_las_cifras_cuadran_con_cada_filtro(self):
        consultas = cargar_consultas(SINTETICAS)
        treks = [[]] + [[t] for t in sorted(consultas["trek"].unique())]
        idiomas = [[]] + [[i] for i in sorted(consultas["idioma"].unique())]
        for meses in PERIODOS.values():
            for t in treks:
                for i in idiomas:
                    datos, *_ = periodo(filtrar(consultas, t, i), meses)
                    if datos.empty:
                        continue
                    with self.subTest(meses=meses, trek=t, idioma=i):
                        m, e = metricas(datos), embudo(datos)
                        me, ct = por_mes_y_estado(datos), cierre_por_trek(datos)
                        self.assertEqual(list(e["numero"].iloc[[0, 1, 3]]),
                                         [m["consultas"], m["respondidas"], m["reservadas"]])
                        self.assertEqual(int(me["consultas"].sum()), m["consultas"])
                        self.assertEqual(int(me.loc[me["estado"] == "sin respuesta", "consultas"].sum()),
                                         m["sin_respuesta"])
                        self.assertEqual(int(ct["consultas"].sum()), m["consultas"])
                        self.assertEqual(int(ct["reservadas"].sum()), m["reservadas"])


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

    def test_orden_de_lectura_y_titulos_con_la_conclusion(self):
        with tempfile.TemporaryDirectory() as carpeta:
            app = abrir_tablero(carpeta)
        titulos = [str(h.proto) for h in app.get("html") if "pregunta" in str(h.proto)]
        orden = ["¿Cómo voy?", "La mayor caída es de", "concentra el", "llega fuera de horario", "mes de viaje",
                 "suman el"]
        posiciones = [next(i for i, t in enumerate(titulos) if frase in t) for frase in orden]
        self.assertEqual(posiciones, sorted(posiciones))


if __name__ == "__main__":
    unittest.main()
