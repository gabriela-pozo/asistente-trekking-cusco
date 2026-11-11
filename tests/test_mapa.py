import tempfile
import unittest
from pathlib import Path

from core import mapa


class PruebasMapa(unittest.TestCase):
    def test_treks_con_datos_reales(self):
        self.assertEqual(mapa.treks_con_mapa(), ["camino_inca", "lares", "salkantay"])

    def test_salkantay(self):
        r = mapa.cargar_ruta("salkantay")
        self.assertEqual(len(r.puntos), 11)
        self.assertEqual(r.de_tipo("inicio")[0].lugar, "Challacancha")
        self.assertEqual([p.orden for p in r.puntos], sorted(p.orden for p in r.puntos))
        self.assertEqual(max(p.altitud_m for p in r.puntos if p.altitud_m), 4630)

    def test_camino_inca_tiene_inicio_y_fin(self):
        r = mapa.cargar_ruta("camino_inca")
        self.assertEqual(r.de_tipo("inicio")[0].lugar, "Km 82 (Piscacucho)")
        self.assertEqual(r.de_tipo("fin")[0].lugar, "Machu Picchu")

    def test_sin_datos_devuelve_none(self):
        for ruta in ("choquequirao", "inca_jungle", "", None, "../x", "no existe"):
            self.assertIsNone(mapa.cargar_ruta(ruta))
        self.assertIsNone(mapa.distancia_recta_km(None))
        self.assertIsNone(mapa.desnivel(None))
        self.assertIsNone(mapa.perfil_altitud(None))
        self.assertIsNone(mapa.enlace_google_maps(None))

    def test_distancia_es_razonable(self):
        km = mapa.distancia_recta_km(mapa.cargar_ruta("salkantay"))
        self.assertTrue(20 < km < 120, km)

    def test_desnivel_con_altitudes(self):
        d = mapa.desnivel(mapa.cargar_ruta("salkantay"))
        self.assertGreater(d["subida_m"], 0)
        self.assertEqual(d["maxima_m"], 4630)
        self.assertLessEqual(d["puntos_con_altitud"], d["puntos"])

    def test_perfil_altitud(self):
        perfil = mapa.perfil_altitud(mapa.cargar_ruta("camino_inca"))
        self.assertEqual(len(perfil), 7)
        self.assertEqual([k for _, k, _ in perfil], sorted(k for _, k, _ in perfil))

    def test_enlace_google_maps(self):
        url = mapa.enlace_google_maps(mapa.cargar_ruta("salkantay"))
        self.assertEqual(url, "https://www.google.com/maps/search/?api=1&query=-13.43295,-72.55832")

    def test_archivo_roto_no_falla(self):
        with tempfile.TemporaryDirectory() as t:
            c = Path(t)
            (c / "rota_3d.csv").write_text("dia,orden,lugar,latitud,longitud\n1,1,A,abc,def\n", encoding="utf-8")
            (c / "corta_2d.csv").write_text("dia,orden,lugar,latitud,longitud,altitud_m,tipo\n"
                                            "1,1,A,-13.1,-72.1,,inicio\n", encoding="utf-8")
            self.assertIsNone(mapa.cargar_ruta("rota", c))
            self.assertIsNone(mapa.cargar_ruta("corta", c))
        self.assertIsNone(mapa.cargar_ruta("salkantay", Path("/no/existe")))


if __name__ == "__main__":
    unittest.main()
