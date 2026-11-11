"""Pruebas de las agregaciones del Tablero por preguntas. Sin llamadas a la API.

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
sys.path.insert(0, str(RAIZ / "scripts"))

import generar_consultas_sinteticas as gen  # noqa: E402
from core.tablero import (  # noqa: E402
    cargar_consultas, cierre_por_trek, embudo, filtrar, fuera_de_horario, hallazgo_embudo, hallazgo_horario,
    hallazgo_meses, hallazgo_paises, hallazgo_treks, paises_con_otros, periodo, por_dia_y_hora, por_mes_y_estado,
    variaciones,
)

SINTETICAS = RAIZ / "data" / "consultas_sinteticas.csv"
APP = str(RAIZ / "app" / "app.py")


def consulta(fecha, estado="cotizada", monto=1000, trek="salkantay", idioma="en", pais="Alemania", mes=5,
             hora="21:10", dia="lunes"):
    return {"fecha_consulta": fecha, "trek": trek, "idioma": idioma, "pais": pais, "mes_viaje": mes,
            "estado": estado, "monto_usd": 0 if estado == "sin respuesta" else monto, "hora_llegada": hora,
            "dia_semana": dia}


def tabla(filas):
    return pd.DataFrame(filas)


class PruebasPeriodo(unittest.TestCase):
    DATOS = tabla([
        consulta("2026-01-15", "reservada", 500),              # anterior al anterior: fuera
        consulta("2026-02-10", "reservada", 800),              # período anterior (feb-abr)
        consulta("2026-04-30", "sin respuesta"),               # período anterior
        consulta("2026-05-01", "reservada", 1200),             # actual (may-jul)
        consulta("2026-06-20", "cotizada", 900),               # actual
        consulta("2026-07-31", "sin respuesta"),               # actual: la más reciente
    ])

    def test_actual_y_anterior_de_igual_largo(self):
        actual, anterior, completo, (desde, hasta) = periodo(self.DATOS, 3)
        self.assertEqual(actual["fecha_consulta"].tolist(), ["2026-05-01", "2026-06-20", "2026-07-31"])
        self.assertEqual(anterior["fecha_consulta"].tolist(), ["2026-02-10", "2026-04-30"])
        self.assertTrue(completo)  # hay datos desde enero: el anterior está completo
        self.assertEqual((str(desde), str(hasta)), ("2026-05-01", "2026-07-31"))

    def test_sin_datos_del_periodo_anterior_completo(self):
        _, _, completo, _ = periodo(self.DATOS, 6)  # el anterior empezaría en agosto de 2025
        self.assertFalse(completo)

    def test_variacion_contra_el_periodo_anterior(self):
        actual, anterior, _, _ = periodo(self.DATOS, 3)
        v = variaciones(actual, anterior)
        self.assertEqual(v["consultas"], 1)
        self.assertAlmostEqual(v["pct_consultas"], 0.5)
        self.assertAlmostEqual(v["tasa_cierre_pp"], (1 / 2 - 1 / 1) * 100)  # 50 % contra 100 %
        self.assertEqual(v["sin_respuesta"], 0)
        self.assertEqual(v["monto_reservado"], 400)

    def test_sin_consultas_antes_no_divide_por_cero(self):
        self.assertIsNone(variaciones(self.DATOS, self.DATOS.iloc[0:0])["pct_consultas"])

    def test_filtros_y_periodo_se_combinan(self):
        datos = pd.concat([self.DATOS, tabla([consulta("2026-07-01", trek="lares", idioma="es")])], ignore_index=True)
        actual, _, _, _ = periodo(filtrar(datos, ["lares"]), 3)
        self.assertEqual(len(actual), 1)
        actual, _, _, _ = periodo(filtrar(datos, idiomas=["en"]), 3)
        self.assertEqual(len(actual), 3)


class PruebasHorario(unittest.TestCase):
    def test_porcentaje_fuera_de_horario(self):
        datos = tabla([consulta("2026-05-01", hora=h) for h in ("07:59", "08:00", "19:59", "20:00", "23:30")])
        pct, n = fuera_de_horario(datos)
        self.assertEqual(n, 5)
        self.assertAlmostEqual(pct, 3 / 5)  # 07:59, 20:00 y 23:30; las 8:00 y las 19:59 están dentro

    def test_sin_hora_no_cuenta(self):
        datos = tabla([consulta("2026-05-01", hora="22:00"), consulta("2026-05-01", hora=None)])
        self.assertEqual(fuera_de_horario(datos), (1.0, 1))
        self.assertEqual(fuera_de_horario(datos.drop(columns="hora_llegada")), (0.0, 0))

    def test_mapa_de_calor_con_las_168_celdas(self):
        datos = tabla([consulta("2026-05-01", hora="21:10", dia="lunes"), consulta("2026-05-02", hora="21:45",
                                                                                      dia="lunes")])
        celdas = por_dia_y_hora(datos)
        self.assertEqual(len(celdas), 7 * 24)
        self.assertEqual(int(celdas["consultas"].sum()), 2)
        self.assertEqual(int(celdas.query("dia == 'lunes' and hora == 21")["consultas"].iloc[0]), 2)

    def test_hallazgo_horario(self):
        datos = tabla([consulta("2026-05-01", hora=h) for h in ("02:00", "21:00", "21:30", "10:00")])
        self.assertEqual(hallazgo_horario(datos), "El 75 % de las consultas llega fuera de horario (antes de las "
                                                  "8:00 o desde las 20:00). La hora con más consultas: de 21:00 a 21:59.")


class PruebasGraficos(unittest.TestCase):
    DATOS = tabla([
        consulta("2026-05-01", "reservada", trek="salkantay", pais="Alemania", mes=7),
        consulta("2026-05-02", "cotizada", trek="salkantay", pais="Alemania", mes=7),
        consulta("2026-05-03", "sin respuesta", trek="salkantay", pais="Francia", mes=6),
        consulta("2026-05-04", "reservada", trek="lares", pais="Brasil", mes=7),
    ])

    def test_cierre_por_trek(self):
        t = cierre_por_trek(self.DATOS)
        self.assertEqual(t["nombre"].tolist(), ["Salkantay", "Lares"])        # más pedido primero
        self.assertEqual(t["consultas"].tolist(), [3, 1])
        self.assertAlmostEqual(t["tasa_cierre"].iloc[0], 1 / 2)               # reservadas / respondidas
        self.assertIn("Salkantay concentra el 75 %", hallazgo_treks(t))

    def test_mes_y_estado(self):
        m = por_mes_y_estado(self.DATOS)
        self.assertEqual(len(m), 12 * 3)                                     # 12 meses × 3 estados presentes
        julio = m[m["mes"] == 7].set_index("estado")["consultas"]
        self.assertEqual((julio["reservada"], julio["cotizada"]), (2, 1))
        self.assertEqual(hallazgo_meses(m), "Julio es el mes de viaje más pedido (3 consultas); "
                                            "el 67 % ya está reservado.")

    def test_paises_top_y_otros_al_final(self):
        p = paises_con_otros(self.DATOS, top=2)
        self.assertEqual(p["pais"].tolist(), ["Alemania", "Brasil", "Otros"])
        self.assertEqual(p["consultas"].tolist(), [2, 1, 1])
        self.assertAlmostEqual(p["porcentaje"].sum(), 1.0)
        self.assertEqual(hallazgo_paises(p), "Alemania y Brasil suman el 75 % de las consultas.")

    def test_embudo(self):
        datos = pd.concat([self.DATOS, tabla([consulta("2026-05-05", "cotizada", monto=0)])], ignore_index=True)
        e = embudo(datos)  # 5 consultas, 4 respondidas, 3 con precio, 2 reservadas
        self.assertEqual(e["numero"].tolist(), [5, 4, 3, 2])
        self.assertTrue(pd.isna(e["pct_anterior"].iloc[0]))  # la primera etapa no tiene anterior
        self.assertEqual([round(x, 2) for x in e["pct_anterior"].iloc[1:]], [0.8, 0.75, 0.67])
        self.assertEqual(hallazgo_embudo(e), "La mayor caída es de cotizadas a reservadas: pasa el 67 %. "
                                             "De cada 100 consultas, 40 terminan en reserva.")

    def test_embudo_vacio(self):
        e = embudo(self.DATOS.iloc[0:0])
        self.assertEqual(e["numero"].tolist(), [0, 0, 0, 0])
        self.assertEqual(hallazgo_embudo(e), "")


class PruebasSinteticasConHora(unittest.TestCase):
    def test_hora_y_dia_coherentes(self):
        df = pd.read_csv(SINTETICAS)
        self.assertTrue(df["hora_llegada"].str.fullmatch(r"([01]\d|2[0-3]):[0-5]\d").all())
        dias = pd.to_datetime(df["fecha_consulta"]).dt.weekday.map(lambda i: gen.DIAS[i])
        self.assertTrue((dias == df["dia_semana"]).all())

    def test_la_noche_de_lima_recibe_consultas(self):
        pct, n = fuera_de_horario(cargar_consultas(SINTETICAS))
        self.assertEqual(n, 300)
        self.assertGreater(pct, .3)  # por la diferencia horaria con Europa y EE. UU.


class PruebasPagina(unittest.TestCase):
    def test_cambiar_periodo_y_filtros(self):
        from streamlit.testing.v1 import AppTest

        with tempfile.TemporaryDirectory() as carpeta, \
                mock.patch.dict(os.environ, {"GEMINI_API_KEY": "", "ABRA_REGISTRO": str(Path(carpeta) / "r.csv")}):
            app = AppTest.from_file(APP, default_timeout=60)
            app.run()
            app.sidebar.radio[0].set_value("Tablero").run()
            app.segmented_control(key="filtro_periodo").set_value("Últimos 12 meses").run()
            self.assertFalse(app.exception)
            self.assertFalse(app.metric[0].delta)  # no hay 12 meses anteriores completos
            app.segmented_control(key="filtro_periodo").set_value("Últimos 3 meses").run()
            app.multiselect[0].set_value(["salkantay"]).run()
            self.assertFalse(app.exception)
            esperado = len(periodo(filtrar(cargar_consultas(SINTETICAS), ["salkantay"]), 3)[0])
            self.assertEqual(app.metric[0].value, str(esperado))
            self.assertEqual(len([e for e in app.main if e.type == "vega_lite_chart"]), 5)
            self.assertEqual(len(app.get("download_button")), 5)  # un CSV por gráfico


if __name__ == "__main__":
    unittest.main()
