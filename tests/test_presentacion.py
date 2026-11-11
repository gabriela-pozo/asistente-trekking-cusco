"""Pruebas del formato de la interfaz (app/presentacion.py). No llaman a ninguna API.

Correr:  python -m unittest discover tests -v
"""
import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "app"))

from ai.schemas import PerfilTurista  # noqa: E402
from core.cotizacion import OpcionCotizada  # noqa: E402
from presentacion import (  # noqa: E402
    fichas_perfil, html_opciones, html_perfil, idioma, lista_markdown, mes, separar_advertencias, usd,
)


class PruebasPresentacion(unittest.TestCase):
    def test_valores_legibles(self):
        self.assertEqual((idioma("en"), idioma("pt"), idioma("xx")), ("Inglés", "Portugués", "XX"))
        self.assertEqual((mes(3), mes(None), mes(13)), ("marzo", "", ""))
        self.assertEqual(usd(1200), "US$ 1 200")

    def test_perfil_sin_codigos(self):
        perfil = PerfilTurista(idioma="en", num_personas=2, mes_viaje=3, treks_de_interes=["salkantay"],
                               datos_faltantes=["fecha exacta"])
        self.assertEqual(dict(fichas_perfil(perfil)),
                         {"Trek": "Salkantay", "Personas": "2", "Mes del viaje": "marzo", "Idioma": "Inglés"})
        self.assertIn("Falta: fecha exacta", html_perfil(perfil))

    def test_duracion_en_rango_y_sin_duplicar_el_mes(self):
        from presentacion import duracion
        perfil = PerfilTurista(idioma="en", mes_viaje=3, fecha_texto="late March", dias_disponibles=5,
                               treks_de_interes=["salkantay"])
        o4 = OpcionCotizada("salkantay_4d", "Salkantay", 4, "estandar", 600, 2)
        o5 = OpcionCotizada("salkantay_5d", "Salkantay", 5, "estandar", 680, 2)
        self.assertEqual(duracion(perfil, [o4, o5]), "4–5 días")
        self.assertEqual(duracion(perfil), "5 días")  # nunca solo "5"
        fichas = dict(fichas_perfil(perfil, [o4, o5]))
        self.assertEqual(fichas["Días"], "4–5 días")
        self.assertEqual(fichas["Mes del viaje"], "marzo")
        self.assertNotIn("Fechas", fichas)  # "late March" repetía "marzo"
        con_fecha = PerfilTurista(idioma="en", mes_viaje=3, fecha_texto="March 20-25")
        self.assertIn("Fechas", dict(fichas_perfil(con_fecha)))

    def test_texto_del_viajero_se_escapa(self):
        perfil = PerfilTurista(idioma="en", fecha_texto="<script>x</script>")
        self.assertNotIn("<script>", html_perfil(perfil))

    def test_opcion_con_precio_y_alternativa(self):
        o = OpcionCotizada("lares_4d", "Lares a Machu Picchu", 4, "estandar", 650, 2, es_alternativa=True)
        html = html_opciones([o])
        self.assertIn("US$ 650", html)
        self.assertIn("Total US$ 1 300", html)
        self.assertIn("Alternativa", html)

    def test_graves_primero_y_dolar_escapado(self):
        graves, revisar = separar_advertencias([
            "Recordar el equipo impermeable.",
            "El mensaje tiene montos que no están en la cotización: [1120]. Corrígelos antes de enviar.",
            "El viajero pidió Choquequirao, que no está en tu tarifario: confírmale el precio.",
        ])
        self.assertEqual(len(graves), 2)
        self.assertEqual(revisar, ["Recordar el equipo impermeable."])
        self.assertEqual(lista_markdown(["Depósito US$ 600"]), "- Depósito US\\$ 600")


if __name__ == "__main__":
    unittest.main()
