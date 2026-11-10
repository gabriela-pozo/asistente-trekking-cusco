"""Pruebas del tarifario generado y de la cotización. No llaman a ninguna API.

Correr:  python -m unittest discover tests -v
"""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "scripts"))

import analisis_precios as ap  # noqa: E402
from core.cotizacion import (  # noqa: E402
    cargar_extras, cargar_tarifario, opciones_para_perfil, precio_por_persona,
)

TARIFARIO = cargar_tarifario(RAIZ / "data" / "tarifario_demo.csv")
EXTRAS = cargar_extras(RAIZ / "data" / "extras_demo.csv")
MERCADO = pd.read_csv(RAIZ / "data" / "precios_mercado.csv")


def perfil(**datos):
    """Perfil mínimo del turista; lo que no se pasa queda como 'sin dato'."""
    base = dict(num_personas=None, mes_viaje=None, dias_disponibles=None, treks_de_interes=[],
                nivel_preferido=None, presupuesto_usd_pp=None, extras_de_interes=[])
    base.update(datos)
    return SimpleNamespace(**base)


def fila(trek_id, nivel):
    return TARIFARIO[(TARIFARIO["trek_id"] == trek_id) & (TARIFARIO["nivel"] == nivel)].iloc[0]


class PruebasTarifario(unittest.TestCase):
    def test_archivo_coincide_con_el_generador(self):
        """Si alguien edita el CSV a mano o cambia las reglas sin regenerar, esta prueba falla."""
        generado = ap.generar_tarifario(MERCADO)
        en_disco = TARIFARIO.copy()
        generado["meses_no_disponible"] = generado["meses_no_disponible"].astype(str)
        pd.testing.assert_frame_equal(en_disco, generado, check_dtype=False)

    def test_estandar_es_mediana_sin_premium(self):
        # Salkantay 5 días: sin la fila premium (1270) la mediana es 674,5 -> 670
        self.assertEqual(fila("salkantay_5d", "estandar")["precio_usd_pp_grupo_2"], 670)
        self.assertEqual(fila("camino_inca_4d", "estandar")["precio_usd_pp_grupo_2"], 840)  # mediana 835 -> 840

    def test_salkantay_4d_no_supera_al_de_5d(self):
        self.assertEqual(fila("salkantay_4d", "estandar")["precio_usd_pp_grupo_2"], 600)  # mediana 595 -> 600 (ya no hace falta la regla del 10 %)
        for nivel in ("economico", "estandar", "premium"):
            self.assertLess(fila("salkantay_4d", nivel)["precio_usd_pp_grupo_2"],
                            fila("salkantay_5d", nivel)["precio_usd_pp_grupo_2"])

    def test_regla_salkantay_4d_con_datos_de_prueba(self):
        """Con los datos reales la regla ya no se activa; aquí se prueba con un mercado inventado."""
        filas = ([("Salkantay", 4, p) for p in (700, 720, 740)]
                 + [("Salkantay", 5, p) for p in (600, 650, 700)]
                 + [("Camino Inca clásico", 4, 800)])
        mercado = pd.DataFrame([{"trek": t, "dias": d, "precio_usd_pp": p, "nivel_aprox": "no_indicado",
                                 "incluir_en_analisis": "si"} for t, d, p in filas])
        estandar, notas = ap.precios_estandar(mercado)
        self.assertEqual(estandar[("Salkantay", 5)], 650)
        self.assertEqual(estandar[("Salkantay", 4)], 590)  # 650 x 0,9 = 585 -> 590, no 720
        self.assertTrue(any("menos 10 %" in n for n in notas))

    def test_economico_y_premium(self):
        self.assertEqual(fila("salkantay_5d", "economico")["precio_usd_pp_grupo_2"], 540)  # 670 x 0,8 = 536
        self.assertEqual(fila("salkantay_5d", "premium")["precio_usd_pp_grupo_2"], 1070)   # 670 x 1,6 = 1072

    def test_descuentos_por_grupo(self):
        f = fila("camino_inca_4d", "estandar")
        self.assertEqual(f["precio_usd_pp_grupo_3a4"], 810)   # 840 x 0,96 = 806,4
        self.assertEqual(f["precio_usd_pp_grupo_5mas"], 770)  # 840 x 0,92 = 772,8

    def test_camino_inca_cerrado_en_febrero(self):
        inca = TARIFARIO[TARIFARIO["ruta"] == "camino_inca"]
        self.assertTrue((inca["meses_no_disponible"] == "2").all())

    def test_redondeo(self):
        self.assertEqual(ap.redondear(812.5), 810)
        self.assertEqual(ap.redondear(815), 820)
        self.assertEqual(ap.redondear(73.5, paso=5), 75)


class PruebasCotizacion(unittest.TestCase):
    def test_precio_segun_tamano_de_grupo(self):
        f = fila("salkantay_5d", "estandar")
        self.assertEqual([precio_por_persona(f, n) for n in (1, 2, 3, 4, 5, 9)],
                         [670, 670, 640, 640, 620, 620])

    def test_salkantay_marzo_dos_personas_sin_preferencia(self):
        opciones = opciones_para_perfil(perfil(num_personas=2, mes_viaje=3, dias_disponibles=5,
                                               treks_de_interes=["salkantay"]), TARIFARIO)
        self.assertTrue(all(o.trek_id.startswith("salkantay") for o in opciones))
        self.assertEqual(opciones[0].nivel, "estandar")  # sin preferencia, primero el estándar
        self.assertEqual((opciones[0].trek_id, opciones[0].precio_pp, opciones[0].total),
                         ("salkantay_4d", 600, 1200))

    def test_dias_disponibles_filtra(self):
        opciones = opciones_para_perfil(perfil(dias_disponibles=4, treks_de_interes=["salkantay"]), TARIFARIO)
        self.assertTrue(all(o.dias == 4 for o in opciones))

    def test_camino_inca_en_febrero_ofrece_salkantay(self):
        opciones = opciones_para_perfil(perfil(mes_viaje=2, treks_de_interes=["camino_inca"]), TARIFARIO)
        self.assertTrue(opciones)
        self.assertTrue(all(o.trek_id.startswith("salkantay") and o.es_alternativa for o in opciones))

    def test_camino_inca_en_marzo_si_se_ofrece(self):
        opciones = opciones_para_perfil(perfil(mes_viaje=3, treks_de_interes=["camino_inca"]), TARIFARIO)
        self.assertEqual(opciones[0].trek_id, "camino_inca_4d")
        self.assertTrue(opciones[0].requiere_permiso)
        self.assertFalse(opciones[0].es_alternativa)

    def test_grupo_de_seis_economico(self):
        opciones = opciones_para_perfil(perfil(num_personas=6, treks_de_interes=["salkantay"],
                                               nivel_preferido="economico"), TARIFARIO)
        self.assertEqual(opciones[0].nivel, "economico")
        self.assertEqual(opciones[0].precio_pp, 440)  # Salkantay 4 días económico, 5 o más
        self.assertEqual(opciones[0].total, 2640)

    def test_grupo_grande_excluye_premium(self):
        opciones = opciones_para_perfil(perfil(num_personas=10, treks_de_interes=["salkantay"],
                                               nivel_preferido="premium"), TARIFARIO)
        self.assertTrue(opciones)
        self.assertTrue(all(o.nivel != "premium" for o in opciones))  # premium: máximo 8

    def test_presupuesto_elige_lo_mas_cercano(self):
        opciones = opciones_para_perfil(perfil(presupuesto_usd_pp=520, dias_disponibles=5,
                                               treks_de_interes=["salkantay"]), TARIFARIO)
        self.assertEqual((opciones[0].trek_id, opciones[0].nivel), ("salkantay_5d", "economico"))

    def test_extras_suman_al_total(self):
        opciones = opciones_para_perfil(
            perfil(num_personas=2, mes_viaje=5, treks_de_interes=["camino_inca"],
                   nivel_preferido="estandar", extras_de_interes=["huayna_picchu", "vistadome"]),
            TARIFARIO, EXTRAS)
        o = opciones[0]
        self.assertEqual(o.precio_pp, 840)
        self.assertEqual(o.precio_pp_con_extras, 840 + 75 + 75)
        self.assertEqual(o.total, 990 * 2)
        self.assertIn("Huayna Picchu", o.resumen())

    def test_premium_no_cobra_vistadome_porque_ya_lo_incluye(self):
        opciones = opciones_para_perfil(
            perfil(treks_de_interes=["camino_inca"], nivel_preferido="premium", extras_de_interes=["vistadome"]),
            TARIFARIO, EXTRAS)
        self.assertEqual(opciones[0].nivel, "premium")
        self.assertEqual(opciones[0].extras, [])

    def test_sin_datos_devuelve_opciones(self):
        opciones = opciones_para_perfil(perfil(), TARIFARIO)
        self.assertEqual(len(opciones), 3)
        self.assertTrue(all(o.personas == 2 for o in opciones))


if __name__ == "__main__":
    unittest.main()
