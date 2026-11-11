"""Pruebas de "Mi semana" (solo consultas registradas en la app). Sin llamadas a la API.

Correr:  python -m unittest discover tests -v
"""
import os
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest import mock

import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from ai.fecha import hoy_en_lima  # noqa: E402
from core.mi_semana import (  # noqa: E402
    cambiar_estado, inicio_semana, leer_registradas, pendientes, progreso_meta, racha, semana,
)
from core.tablero import COLUMNAS, COLUMNAS_REGISTRO  # noqa: E402

HOY = date(2026, 11, 12)  # jueves; la semana empieza el lunes 9
APP = str(RAIZ / "app" / "app.py")


def fila(n, dia, estado="cotizada", monto=1000, fecha_estado=None, trek="salkantay", personas=2):
    return {"id": f"R{n:03d}", "fecha_consulta": dia.isoformat(), "trek": trek, "pais": "no indicado",
            "idioma": "en", "mes_viaje": 3, "personas": personas, "nivel": "economico", "estado": estado,
            "monto_usd": monto, "fecha_estado": (fecha_estado or dia).isoformat()}


class ConArchivo(unittest.TestCase):
    def setUp(self):
        self.carpeta = tempfile.TemporaryDirectory()
        self.ruta = Path(self.carpeta.name) / "registradas.csv"

    def tearDown(self):
        self.carpeta.cleanup()

    def guardar(self, filas, columnas=COLUMNAS_REGISTRO):
        pd.DataFrame(filas)[columnas].to_csv(self.ruta, index=False)
        return leer_registradas(self.ruta)


class PruebasMeta(ConArchivo):
    def test_cuenta_solo_esta_semana(self):
        df = self.guardar([fila(1, date(2026, 11, 8)),            # domingo anterior: no cuenta
                           fila(2, date(2026, 11, 9)), fila(3, date(2026, 11, 10)),
                           fila(4, HOY, estado="reservada")])
        meta = progreso_meta(df, HOY, 20)
        self.assertEqual((meta.respondidas, meta.faltan, meta.cumplida), (3, 17, False))
        self.assertAlmostEqual(meta.fraccion, 0.15)

    def test_meta_cumplida_y_barra_no_pasa_de_100(self):
        df = self.guardar([fila(i, HOY) for i in range(1, 6)])
        meta = progreso_meta(df, HOY, 4)
        self.assertEqual((meta.respondidas, meta.faltan, meta.cumplida, meta.fraccion), (5, 0, True, 1.0))

    def test_sin_registros(self):
        meta = progreso_meta(leer_registradas(self.ruta), HOY, 20)
        self.assertEqual((meta.respondidas, meta.faltan, meta.cumplida), (0, 20, False))

    def test_semana_empieza_el_lunes(self):
        self.assertEqual(inicio_semana(HOY), date(2026, 11, 9))
        self.assertEqual(inicio_semana(date(2026, 11, 9)), date(2026, 11, 9))
        self.assertEqual(inicio_semana(date(2026, 11, 15)), date(2026, 11, 9))


class PruebasRacha(ConArchivo):
    def test_dias_seguidos_hasta_hoy(self):
        df = self.guardar([fila(i, HOY - timedelta(days=i)) for i in range(4)])  # hoy y 3 días antes
        self.assertEqual((racha(df, HOY).dias, racha(df, HOY).registro_hoy), (4, True))

    def test_un_dia_sin_registros_la_corta(self):
        dias = [HOY, HOY - timedelta(days=1), HOY - timedelta(days=3), HOY - timedelta(days=4)]  # falta anteayer
        df = self.guardar([fila(i, d) for i, d in enumerate(dias)])
        self.assertEqual(racha(df, HOY).dias, 2)

    def test_si_hoy_no_registro_la_racha_de_ayer_sigue(self):
        df = self.guardar([fila(1, HOY - timedelta(days=1)), fila(2, HOY - timedelta(days=2))])
        r = racha(df, HOY)
        self.assertEqual((r.dias, r.registro_hoy), (2, False))

    def test_si_ayer_tampoco_la_racha_es_cero(self):
        df = self.guardar([fila(1, HOY - timedelta(days=2))])
        self.assertEqual(racha(df, HOY).dias, 0)

    def test_varias_consultas_el_mismo_dia_cuentan_un_dia(self):
        df = self.guardar([fila(1, HOY), fila(2, HOY), fila(3, HOY)])
        self.assertEqual(racha(df, HOY).dias, 1)


class PruebasPendientes(ConArchivo):
    def test_cotizadas_hace_mas_de_2_dias(self):
        df = self.guardar([
            fila(1, HOY - timedelta(days=5)),                          # espera
            fila(2, HOY - timedelta(days=3)),                          # espera
            fila(3, HOY - timedelta(days=2)),                          # 2 días justos: todavía no
            fila(4, HOY),                                              # de hoy
            fila(5, HOY - timedelta(days=6), estado="reservada"),      # ya cerrada
            fila(6, HOY - timedelta(days=6), estado="perdida"),        # ya cerrada
        ])
        self.assertEqual(pendientes(df, HOY)["id"].tolist(), ["R001", "R002"])

    def test_marcar_como_reservada_o_perdida(self):
        self.guardar([fila(1, HOY - timedelta(days=5)), fila(2, HOY - timedelta(days=4))])
        cambiar_estado(self.ruta, "R001", "reservada", HOY)
        cambiar_estado(self.ruta, "R002", "perdida", HOY)
        df = leer_registradas(self.ruta)
        self.assertEqual(df["estado"].tolist(), ["reservada", "perdida"])
        self.assertEqual(df["fecha_estado"].tolist(), [HOY, HOY])
        self.assertEqual(df["fecha_consulta"].tolist(), [HOY - timedelta(days=5), HOY - timedelta(days=4)])
        self.assertTrue(pendientes(df, HOY).empty)
        self.assertEqual(semana(df, HOY).esta, 1000)  # cuenta en la semana en que se reservó

    def test_estado_no_valido(self):
        self.guardar([fila(1, HOY)])
        with self.assertRaises(ValueError):
            cambiar_estado(self.ruta, "R001", "cotizada", HOY)

    def test_registros_sin_fecha_estado_usan_la_fecha_de_consulta(self):
        df = self.guardar([fila(1, HOY - timedelta(days=4))], columnas=COLUMNAS)
        self.assertEqual(df["fecha_estado"].tolist(), [HOY - timedelta(days=4)])
        self.assertEqual(len(pendientes(df, HOY)), 1)


class PruebasSemana(ConArchivo):
    def test_esta_semana_contra_la_anterior(self):
        df = self.guardar([fila(1, HOY, "reservada", 1200), fila(2, HOY, "cotizada", 900),
                           fila(3, date(2026, 11, 4), "reservada", 500)])
        s = semana(df, HOY)
        self.assertEqual((s.esta, s.anterior, s.variacion), (1200, 500, 700))

    def test_supera_su_mejor_semana(self):
        df = self.guardar([fila(1, date(2026, 10, 20), "reservada", 1500),   # su mejor semana
                           fila(2, date(2026, 11, 3), "reservada", 800),
                           fila(3, HOY, "reservada", 1000)])
        s = semana(df, HOY)
        self.assertEqual(s.mejor_anterior, 1500)
        self.assertFalse(s.supera_mejor)
        df = self.guardar([fila(1, date(2026, 10, 20), "reservada", 1500), fila(2, date(2026, 11, 3), "reservada", 800),
                           fila(3, HOY, "reservada", 1000), fila(4, HOY, "reservada", 600)])
        self.assertTrue(semana(df, HOY).supera_mejor)  # 1600 > 1500

    def test_la_primera_semana_no_es_un_hito(self):
        df = self.guardar([fila(1, HOY, "reservada", 1000)])
        self.assertFalse(semana(df, HOY).supera_mejor)  # no hay con qué compararse todavía


class PruebasPagina(ConArchivo):
    def correr(self):
        from streamlit.testing.v1 import AppTest

        with mock.patch.dict(os.environ, {"GEMINI_API_KEY": "", "ABRA_REGISTRO": str(self.ruta)}):
            app = AppTest.from_file(APP, default_timeout=60)
            app.run()
            app.sidebar.radio[0].set_value("Tablero").run()
        self.assertFalse(app.exception)
        return app

    def test_estado_vacio_lleva_a_nueva_consulta(self):
        app = self.correr()
        self.assertTrue(any("Registra tus consultas y aquí verás" in m.value for m in app.markdown))
        with mock.patch.dict(os.environ, {"GEMINI_API_KEY": "", "ABRA_REGISTRO": str(self.ruta)}):
            next(b for b in app.button if b.label == "Ir a Nueva consulta").click().run()
        self.assertEqual(app.sidebar.radio[0].value, "Nueva consulta")
        self.assertEqual(app.header[0].value, "Nueva consulta")

    def test_con_registros_muestra_semana_meta_y_seguimiento(self):
        hoy = hoy_en_lima()  # la app usa la fecha real de Lima: el archivo se arma alrededor de ella
        self.guardar([fila(1, hoy, "reservada", 1200), fila(2, hoy - timedelta(days=5)),
                      fila(3, hoy - timedelta(days=7), "reservada", 500)])
        app = self.correr()
        semana_metric = next(m for m in app.metric if m.label == "Reservados esta semana")
        self.assertTrue(semana_metric.value.startswith("US$") and semana_metric.value.endswith("200"))
        self.assertTrue(any("respondidas esta semana" in str(p.proto) for p in app.get("progress")))
        self.assertTrue(any("espera seguimiento" in m.value for m in app.markdown))
        app.button(key="reservar_R002").click().run()
        self.assertFalse(app.exception)
        self.assertEqual(leer_registradas(self.ruta).set_index("id").loc["R002", "estado"], "reservada")


if __name__ == "__main__":
    unittest.main()
