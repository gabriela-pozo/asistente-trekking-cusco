"""Pruebas de "Armar paquete": unidades, extras por trek, sugerencias, recargo y control de precios.
No llaman a la API: el modelo es simulado.

Correr:  python -m unittest discover tests -v
"""
import os
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from ai import prompts  # noqa: E402
from ai.ejemplo import cargar_ejemplo  # noqa: E402
from ai.knowledge import BaseConocimiento  # noqa: E402
from ai.llm import Uso  # noqa: E402
from ai.pipeline import aplicar_paquete, precios_en_texto, procesar_consulta  # noqa: E402
from ai.schemas import BorradorRespuesta, ExtraSugerido, PerfilTurista  # noqa: E402
from core.cotizacion import cargar_extras, cargar_tarifario, opciones_para_perfil  # noqa: E402
from core.paquete import (  # noqa: E402
    MAXIMO_SUGERIDOS, Seleccion, armar_paquete, extras_aplicables, fila_del_trek, noches_sugeridas,
    sugeridos_validos, texto_paquete,
)

TARIFARIO = cargar_tarifario(RAIZ / "data" / "tarifario_demo.csv")
EXTRAS = cargar_extras(RAIZ / "data" / "extras_demo.csv")
APP = str(RAIZ / "app" / "app.py")


def opciones(trek="salkantay", personas=2, **perfil):
    datos = dict(idioma="en", num_personas=personas, treks_de_interes=[trek], nivel_preferido="estandar") | perfil
    return opciones_para_perfil(PerfilTurista.model_validate(datos), TARIFARIO, maximo=2)


def paquete(extras=(), noches=0, estrellas=3, metodo="transferencia", personas=2, trek="salkantay", recargos=None):
    return armar_paquete(opciones(trek, personas), TARIFARIO, EXTRAS,
                         Seleccion(extras=list(extras), noches_cusco=noches, estrellas=estrellas, metodo_pago=metodo),
                         recargos)


def aplicables(trek):
    return set(extras_aplicables(EXTRAS, fila_del_trek(opciones(trek)[0], TARIFARIO))["extra_id"])


class PruebasDatos(unittest.TestCase):
    def test_columnas_y_unidades(self):
        self.assertEqual(list(EXTRAS.columns), ["extra_id", "extra", "unidad", "precio_usd", "aplica_a",
                                                "beneficio_para_el_viajero", "origen_precio"])
        self.assertTrue(set(EXTRAS["unidad"]) <= {"por persona", "por noche", "por grupo"})
        self.assertTrue(EXTRAS["origen_precio"].str.len().gt(0).all())  # cada precio dice de dónde sale

    def test_precios_con_fuente(self):
        precio = EXTRAS.set_index("extra_id")["precio_usd"]
        self.assertEqual(precio["bolsa_dormir"], 27.5)   # mediana de US$ 25 y US$ 30
        self.assertEqual(precio["bastones"], 22.5)       # mediana de US$ 25 y US$ 20
        self.assertEqual(precio["huayna_picchu"], 60)
        origen = EXTRAS.set_index("extra_id")["origen_precio"]
        for supuesto in ("hotel_cusco_3", "hotel_cusco_4", "traslado_aeropuerto"):
            self.assertIn("Supuesto de la agencia demo", origen[supuesto])


class PruebasUnidades(unittest.TestCase):
    def test_por_persona(self):
        p = paquete(["bolsa_dormir"])
        bolsa = p.extras[0]
        self.assertEqual((bolsa.precio_c, bolsa.veces, bolsa.total_c), (2750, 2, 5500))
        self.assertEqual(p.subtotal_c, 1200_00 + 55_00)

    def test_por_noche_hotel_en_cusco(self):
        p = paquete(noches=2, estrellas=4)
        hotel = next(c for c in p.modulo if c.id == "hotel_cusco_4")
        self.assertEqual(hotel.total_c, 75_00 * 2 * 2)   # US$ 75 x 2 personas x 2 noches

    def test_por_noche_habitacion_individual_cuenta_todo_el_viaje(self):
        p = paquete(["habitacion_individual"], noches=1, personas=1)
        individual = p.extras[0]
        self.assertEqual(individual.noches, 1 + 3)        # 1 noche en Cusco + 3 noches del trek de 4 días
        self.assertEqual(individual.total_c, 100_00 * 4)

    def test_por_grupo_se_cobra_una_vez(self):
        p = paquete(noches=1)
        traslado = next(c for c in p.modulo if c.id == "traslado_aeropuerto")
        self.assertEqual((traslado.veces, traslado.total_c), (1, 25_00))
        self.assertEqual(p.subtotal_c, 1200_00 + 40_00 * 2 + 25_00)
        self.assertEqual(p.por_persona_c, (1200_00 + 80_00 + 25_00) // 2)

    def test_sin_noches_no_hay_modulo(self):
        self.assertEqual(paquete(noches=0).modulo, [])


class PruebasExtrasPorTrek(unittest.TestCase):
    def test_extras_que_no_aplican_no_aparecen(self):
        self.assertIn("caballo", aplicables("salkantay"))
        self.assertNotIn("caballo", aplicables("lares"))
        self.assertNotIn("huayna_picchu", aplicables("choquequirao"))  # no llega a Machu Picchu
        self.assertNotIn("bolsa_dormir", aplicables("inca_jungle"))    # no acampa
        self.assertIn("huayna_picchu", aplicables("inca_jungle"))

    def test_el_modulo_de_cusco_no_es_un_extra(self):
        for trek in ("salkantay", "camino_inca", "choquequirao"):
            self.assertFalse(aplicables(trek) & {"hotel_cusco_3", "hotel_cusco_4", "traslado_aeropuerto"})

    def test_extra_marcado_que_no_aplica_no_se_cobra(self):
        p = paquete(["huayna_picchu", "caballo"], trek="choquequirao", personas=1)
        self.assertEqual(p.extras, [])
        self.assertEqual(p.subtotal_c, p.base_c)


class PruebasSugerencias(unittest.TestCase):
    FILA = fila_del_trek(opciones()[0], TARIFARIO)

    def sugerido(self, extra_id):
        return ExtraSugerido(extra_id=extra_id, beneficio="b", motivo="m")

    def test_maximo_3_y_solo_de_la_lista(self):
        pedidos = [self.sugerido(i) for i in ("bolsa_dormir", "inventado", "bastones", "bolsa_dormir",
                                               "caballo", "huayna_picchu", "servicio_privado")]
        validos = sugeridos_validos(pedidos, EXTRAS, self.FILA)
        self.assertEqual([s.extra_id for s in validos], ["bolsa_dormir", "bastones", "caballo"])
        self.assertEqual(MAXIMO_SUGERIDOS, 3)

    def test_no_sugiere_lo_que_no_aplica_al_trek(self):
        fila = fila_del_trek(opciones("choquequirao")[0], TARIFARIO)
        validos = sugeridos_validos([self.sugerido("huayna_picchu"), self.sugerido("hotel_cusco_3")], EXTRAS, fila)
        self.assertEqual(validos, [])

    def test_noches_sugeridas(self):
        base = PerfilTurista.model_validate({"idioma": "en"})
        self.assertEqual(noches_sugeridas(base), 1)                                        # no dice cuándo llega
        self.assertEqual(noches_sugeridas(base.model_copy(update={"llega_a_cusco": "mismo_dia"})), 1)
        self.assertEqual(noches_sugeridas(base.model_copy(update={"llega_a_cusco": "antes"})), 0)

    def test_el_modelo_recibe_la_lista_de_extras_sin_precios(self):
        sistema = prompts.sistema_extraer("martes 10 de noviembre de 2026", prompts.lista_extras(EXTRAS))
        self.assertIn("EXTRAS DE LA AGENCIA", sistema)
        self.assertIn("bolsa_dormir: Alquiler de bolsa de dormir", sistema)
        self.assertIn("máximo 3", sistema)
        self.assertNotIn("27.5", sistema)
        self.assertNotIn("hotel_cusco_3", sistema)  # el módulo de Cusco lo sugiere el código


class PruebasRecargo(unittest.TestCase):
    def test_sin_recargo_con_transferencia(self):
        p = paquete()
        self.assertEqual((p.recargo_c, p.total_c, p.deposito_c), (0, 1200_00, 600_00))

    def test_tarjeta_5_y_paypal_8_por_ciento(self):
        tarjeta, paypal = paquete(metodo="tarjeta"), paquete(metodo="paypal")
        self.assertEqual((tarjeta.recargo_c, tarjeta.total_c), (60_00, 1260_00))
        self.assertEqual((paypal.recargo_c, paypal.total_c), (96_00, 1296_00))
        self.assertEqual(paypal.deposito_c, 648_00)  # el depósito es el 50 % del total con recargo

    def test_recargo_editable(self):
        p = paquete(metodo="tarjeta", recargos={"transferencia": 0, "tarjeta": 4.5, "paypal": 8})
        self.assertEqual(p.recargo_c, 54_00)


class PruebasBorrador(unittest.TestCase):
    def setUp(self):
        self.resultado, _ = cargar_ejemplo()
        sugeridos = [ExtraSugerido(extra_id="bolsa_dormir", beneficio="you said you have no gear", motivo="no tiene equipo")]
        self.resultado.perfil = self.resultado.perfil.model_copy(update={"extras_sugeridos": sugeridos})
        self.p = armar_paquete(self.resultado.opciones, TARIFARIO, EXTRAS,
                               Seleccion(extras=["bolsa_dormir", "huayna_picchu"], noches_cusco=1, metodo_pago="tarjeta"))
        self.con_paquete = aplicar_paquete(self.resultado, self.p)
        self.texto = self.con_paquete.borrador.mensaje_para_cliente

    def test_una_linea_por_componente_con_su_beneficio(self):
        lineas = self.texto.splitlines()
        self.assertIn("• Salkantay, 4 days, standard: US$ 600 per person", lineas)
        self.assertIn("• Sleeping bag rental: US$ 27.50 per person (you said you have no gear)", lineas)  # el del modelo
        self.assertIn("• Huayna Picchu entrance: US$ 60 per person (the best view of Machu Picchu from above)", lineas)
        self.assertTrue(any(linea.startswith("• 1 night at a 3★ hotel in Cusco") for linea in lineas))

    def test_totales_recargo_y_deposito(self):
        self.assertIn("Total: US$ 740 per person, US$ 1480 for the group.", self.texto)
        self.assertIn("Paying by card: +5 % (US$ 74). Total to pay: US$ 1554.", self.texto)
        self.assertIn("Deposit US$ 777 (50 %) to book; balance US$ 777", self.texto)

    def test_no_elegidos_como_opcional_en_una_linea(self):
        opcional = [linea for linea in self.texto.splitlines() if linea.startswith("Optional:")]
        self.assertEqual(len(opcional), 1)
        for nombre in ("Trekking poles rental US$ 22.50 per person", "Single room US$ 100 per night",
                       "Private service US$ 100 per person"):
            self.assertIn(nombre, opcional[0])
        self.assertNotIn("Sleeping bag", opcional[0])

    def test_quita_las_lineas_de_precio_del_modelo(self):
        self.assertNotIn("US$ 1200)", self.texto)            # "4-day trek: US$ 600 per person (Total US$ 1200)."
        self.assertEqual(self.texto.count("Deposit"), 1)    # solo el depósito del paquete
        self.assertIn("Another option: Salkantay, 5 days, standard: US$ 680 per person.", self.texto)

    def test_control_acepta_los_montos_del_paquete(self):
        self.assertEqual(self.con_paquete.precios_no_autorizados, [])
        self.assertFalse(any("no coincide" in a or "palabras" in a for a in self.con_paquete.advertencias),
                         self.con_paquete.advertencias)

    def test_control_rechaza_un_monto_que_no_calculo_el_codigo(self):
        inventado = self.resultado.borrador.model_copy(update={
            "mensaje_para_cliente": self.resultado.borrador.mensaje_para_cliente + " Porters cost US$ 33.50 extra."})
        self.resultado.borrador = inventado
        r = aplicar_paquete(self.resultado, self.p)
        self.assertEqual(r.precios_no_autorizados, [33.5])
        self.assertTrue(any("33.5" in a for a in r.advertencias))

    def test_volver_a_armar_parte_del_mensaje_del_modelo(self):
        sin_extras = armar_paquete(self.resultado.opciones, TARIFARIO, EXTRAS, Seleccion())
        otra_vez = aplicar_paquete(self.con_paquete, sin_extras).borrador.mensaje_para_cliente
        self.assertNotIn("Sleeping bag rental:", otra_vez)
        self.assertEqual(otra_vez.count("Your package"), 1)

    def test_en_espanol(self):
        perfil = self.resultado.perfil.model_copy(update={"idioma": "es", "extras_sugeridos": []})
        texto = texto_paquete(self.p, perfil.idioma)
        self.assertIn("• Alquiler de bolsa de dormir: US$ 27,50 por persona", texto)
        self.assertIn("Pago con tarjeta: +5 % (US$ 74). Total a pagar: US$ 1554.", texto)

    def test_montos_con_centavos(self):
        self.assertEqual(precios_en_texto("US$ 27.50, US$ 27,50, US$ 1,360 y 1.360 USD; US$ 600."),
                         [27.5, 27.5, 1360, 1360, 600])


class PruebasFlujo(unittest.TestCase):
    def test_el_modelo_sugiere_y_el_codigo_arma_el_paquete(self):
        perfil = {"idioma": "en", "num_personas": 1, "mes_viaje": 6, "treks_de_interes": ["salkantay"],
                  "llega_a_cusco": "mismo_dia",
                  "extras_sugeridos": [{"extra_id": "bolsa_dormir", "beneficio": "you have no gear", "motivo": "no tiene equipo"},
                                       {"extra_id": "habitacion_individual", "beneficio": "your own room", "motivo": "viaja solo"}]}
        borrador = {"idioma": "en", "mensaje_para_cliente": "Hi!\nSalkantay 4 days: US$ 600.\nIncluded: guide.\nWhich date?",
                    "preguntas_al_turista": ["Which date?"], "advertencias_para_agencia": []}

        class LLM:
            def estructurado(self, sistema, mensaje, esquema):
                datos = perfil if esquema is PerfilTurista else borrador
                return esquema.model_validate(datos), Uso(10, 5)

        r = procesar_consulta("Hi! Solo traveler, no gear, landing in Cusco the day of the trek.", LLM(),
                              BaseConocimiento(RAIZ / "data" / "knowledge"), TARIFARIO, EXTRAS, hoy=date(2026, 11, 10))
        fila = fila_del_trek(r.opciones[0], TARIFARIO)
        sugeridos = [s.extra_id for s in sugeridos_validos(r.perfil.extras_sugeridos, EXTRAS, fila)]
        p = armar_paquete(r.opciones, TARIFARIO, EXTRAS,
                          Seleccion(extras=sugeridos, noches_cusco=noches_sugeridas(r.perfil)))
        final = aplicar_paquete(r, p)
        self.assertEqual(sugeridos, ["bolsa_dormir", "habitacion_individual"])
        self.assertIn("(your own room)", final.borrador.mensaje_para_cliente)
        self.assertIn("1 night at a 3★ hotel in Cusco", final.borrador.mensaje_para_cliente)
        self.assertEqual(final.precios_no_autorizados, [])


class PruebasPaginaPaquete(unittest.TestCase):
    def test_marcar_extras_y_pagar_con_paypal_rearma_el_borrador(self):
        from streamlit.testing.v1 import AppTest

        with tempfile.TemporaryDirectory() as carpeta, \
                mock.patch.dict(os.environ, {"GEMINI_API_KEY": "", "ABRA_REGISTRO": str(Path(carpeta) / "r.csv")}):
            app = AppTest.from_file(APP, default_timeout=30)
            app.run()
            next(b for b in app.button if b.label == "Usar mensaje de ejemplo").click().run()
            self.assertIn("Your package for 2 people:", app.text_area(key="borrador").value)
            self.assertIn("1 night at a 3★ hotel", app.text_area(key="borrador").value)  # no dice cuándo llega
            app.checkbox(key="w_extra_bolsa_dormir").check().run()
            app.radio(key="w_metodo").set_value("PayPal (+8 %)").run()
        self.assertFalse(app.exception)
        borrador = app.text_area(key="borrador").value
        self.assertIn("Sleeping bag rental: US$ 27.50 per person", borrador)
        self.assertIn("Paying by PayPal: +8 %", borrador)
        self.assertTrue(any("Recargo por pago con PayPal" in str(h.proto) for h in app.get("html")))


if __name__ == "__main__":
    unittest.main()
