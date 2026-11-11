"""Pruebas del Tablero: datos sintéticos, agregaciones y registro desde la app. No llaman a la API.

Correr:  python -m unittest discover tests -v
"""
import os
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "scripts"))

import generar_consultas_sinteticas as gen  # noqa: E402
from ai.ejemplo import cargar_ejemplo  # noqa: E402
from core.cotizacion import cargar_tarifario  # noqa: E402
from core.tablero import (  # noqa: E402
    COLUMNAS, COLUMNAS_REGISTRO, cargar_consultas, filtrar, metricas, por_mes_viaje, por_pais, por_trek, registrar,
    registro_desde_resultado,
)

SINTETICAS = RAIZ / "data" / "consultas_sinteticas.csv"
APP = str(RAIZ / "app" / "app.py")


def tabla(filas):
    return pd.DataFrame([dict(zip(["trek", "idioma", "pais", "mes_viaje", "estado", "monto_usd"], f)) for f in filas])


PEQUENA = tabla([
    ("salkantay", "en", "Alemania", 5, "reservada", 1200),
    ("salkantay", "es", "España", 5, "cotizada", 600),
    ("camino_inca", "en", "Alemania", 7, "reservada", 1680),
    ("lares", "en", "Francia", 7, "sin respuesta", 0),
])


class PruebasAgregacion(unittest.TestCase):
    def test_metricas(self):
        m = metricas(PEQUENA)
        self.assertEqual((m["consultas"], m["reservadas"], m["respondidas"], m["sin_respuesta"]), (4, 2, 3, 1))
        self.assertAlmostEqual(m["tasa_cierre"], 2 / 3)       # reservadas / respondidas
        self.assertAlmostEqual(m["pct_sin_respuesta"], 0.25)
        self.assertEqual(m["monto_reservado"], 2880)           # solo las reservadas

    def test_metricas_vacias_no_dividen_por_cero(self):
        m = metricas(PEQUENA.iloc[0:0])
        self.assertEqual((m["consultas"], m["tasa_cierre"], m["pct_sin_respuesta"]), (0, 0.0, 0.0))

    def test_filtrar(self):
        self.assertEqual(len(filtrar(PEQUENA, ["salkantay"])), 2)
        self.assertEqual(len(filtrar(PEQUENA, idiomas=["en"])), 3)
        self.assertEqual(len(filtrar(PEQUENA, ["salkantay"], ["en"])), 1)
        self.assertEqual(len(filtrar(PEQUENA, [], [])), 4)     # sin selección = todos

    def test_por_mes_tiene_los_12_meses(self):
        meses = por_mes_viaje(PEQUENA)
        self.assertEqual(len(meses), 12)
        self.assertEqual(meses.set_index("mes").loc[[5, 7, 1], "consultas"].tolist(), [2, 2, 0])
        self.assertEqual(meses["mes_nombre"].iloc[0], "Ene")

    def test_por_trek_y_pais_con_nombres_legibles(self):
        self.assertEqual(por_trek(PEQUENA).iloc[0].tolist(), ["Salkantay", 2])
        self.assertIn("Camino Inca clásico", por_trek(PEQUENA)["trek"].tolist())
        self.assertEqual(por_pais(PEQUENA).iloc[0].tolist(), ["Alemania", 2])
        self.assertEqual(len(por_pais(PEQUENA, maximo=2)), 2)


class PruebasSinteticas(unittest.TestCase):
    def test_archivo_coincide_con_el_generador(self):
        generado = gen.generar(cargar_tarifario(RAIZ / "data" / "tarifario_demo.csv"))
        pd.testing.assert_frame_equal(pd.read_csv(SINTETICAS), generado, check_dtype=False)

    def test_rango_y_tamano(self):
        df = pd.read_csv(SINTETICAS)
        self.assertEqual(len(df), 300)
        self.assertEqual(list(df.columns), COLUMNAS)
        self.assertGreaterEqual(df["fecha_consulta"].min(), "2025-09-01")
        self.assertLessEqual(df["fecha_consulta"].max(), "2026-10-31")
        self.assertTrue(set(df["estado"]) <= {"cotizada", "reservada", "sin respuesta"})

    def test_sin_datos_de_personas(self):
        df = pd.read_csv(SINTETICAS)
        for columna in ("nombre", "telefono", "email", "mensaje", "texto"):
            self.assertNotIn(columna, df.columns)

    def test_coherencia(self):
        df = pd.read_csv(SINTETICAS)
        self.assertTrue((df.loc[df["estado"] == "sin respuesta", "monto_usd"] == 0).all())
        self.assertTrue((df.loc[df["estado"] != "sin respuesta", "monto_usd"] > 0).all())
        cerrado = df[(df["mes_viaje"] == 2) & df["trek"].isin(["camino_inca", "camino_inca_corto"])]
        self.assertTrue(cerrado.empty)  # el Camino Inca cierra en febrero


class PruebasRegistro(unittest.TestCase):
    def test_registro_sin_texto_ni_telefono(self):
        resultado, datos = cargar_ejemplo()
        fila = registro_desde_resultado(resultado, "reservada", date(2026, 11, 10), 1)
        self.assertEqual(list(fila), COLUMNAS_REGISTRO)
        self.assertEqual((fila["trek"], fila["idioma"], fila["mes_viaje"], fila["estado"], fila["monto_usd"]),
                         ("salkantay", "en", 3, "reservada", 1200))
        texto = " ".join(str(v) for v in fila.values())
        self.assertNotIn(datos["consulta"][:20], texto)
        self.assertNotIn("Hi", texto)

    def test_estado_invalido(self):
        resultado, _ = cargar_ejemplo()
        with self.assertRaises(ValueError):
            registro_desde_resultado(resultado, "vendida", date(2026, 11, 10), 1)

    def test_registrar_y_leer_junto_a_las_sinteticas(self):
        resultado, _ = cargar_ejemplo()
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = Path(carpeta) / "registradas.csv"
            self.assertEqual(registrar(registro_desde_resultado(resultado, "cotizada", date(2026, 11, 10), 1), ruta), 1)
            self.assertEqual(registrar(registro_desde_resultado(resultado, "reservada", date(2026, 11, 10), 2), ruta), 2)
            todas = cargar_consultas(SINTETICAS, ruta)
            self.assertEqual(len(todas), 302)
            self.assertEqual((todas["origen"] == "registrada").sum(), 2)
            self.assertEqual(cargar_consultas(SINTETICAS, Path(carpeta) / "no_existe.csv")["origen"].unique().tolist(),
                             ["sintética"])


class PruebasPaginaTablero(unittest.TestCase):
    def test_pagina_con_etiqueta_metricas_y_graficos(self):
        from streamlit.testing.v1 import AppTest

        with tempfile.TemporaryDirectory() as carpeta, \
                mock.patch.dict(os.environ, {"GEMINI_API_KEY": "", "ABRA_REGISTRO": str(Path(carpeta) / "r.csv")}):
            app = AppTest.from_file(APP, default_timeout=30)
            app.run()
            app.sidebar.radio[0].set_value("Tablero").run()
        self.assertFalse(app.exception)
        self.assertEqual(app.header[0].value, "Tablero")
        self.assertEqual([m.label for m in app.metric], ["Consultas", "Tasa de cierre", "Sin respuesta", "Monto reservado"])
        self.assertEqual(app.metric[0].value, "300")
        self.assertTrue(any("Datos sintéticos del demo: no son de ninguna agencia real" in str(h.proto)
                            for h in app.get("html")))
        self.assertEqual(len([e for e in app.main if e.type == "vega_lite_chart"]), 3)

    def test_boton_registrar_guarda_solo_el_perfil(self):
        from streamlit.testing.v1 import AppTest

        with tempfile.TemporaryDirectory() as carpeta:
            ruta = Path(carpeta) / "r.csv"
            with mock.patch.dict(os.environ, {"GEMINI_API_KEY": "", "ABRA_REGISTRO": str(ruta)}):
                app = AppTest.from_file(APP, default_timeout=30)
                app.run()
                next(b for b in app.button if b.label == "Usar mensaje de ejemplo").click().run()
                app.button(key="registrar_reservada").click().run()
            self.assertFalse(app.exception)
            guardado = pd.read_csv(ruta)
            self.assertEqual(guardado[["trek", "estado", "monto_usd"]].iloc[0].tolist(), ["salkantay", "reservada", 1200])
            self.assertEqual(list(guardado.columns), COLUMNAS_REGISTRO)
            self.assertTrue(app.button(key="registrar_cotizada").disabled)  # no se registra dos veces


if __name__ == "__main__":
    unittest.main()
