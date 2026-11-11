"""Pruebas de la trazabilidad (fuentes, fechas, versión de la base, conteo de pruebas). Sin llamadas a la API.

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

from ai.knowledge import Fragmento, cargar_fragmentos  # noqa: E402
from ai.trazabilidad import (  # noqa: E402
    antiguedad, buscar_en_base, consultas_restantes, contar_pruebas, es_oficial, fuentes_usadas, hay_que_verificar,
    modelos_configurados, referencia_cuota, tabla_base, version_base,
)

CARPETA = RAIZ / "data" / "knowledge"
HOY = date(2026, 11, 11)


class PruebasFechas(unittest.TestCase):
    def test_antiguedad_en_dias(self):
        self.assertEqual(antiguedad("2026-11-01", HOY), 10)
        self.assertIsNone(antiguedad("", HOY))
        self.assertIsNone(antiguedad("noviembre", HOY))

    def test_mas_de_90_dias_hay_que_verificar(self):
        self.assertFalse(hay_que_verificar("2026-08-13", HOY))  # 90 días justos: todavía vale
        self.assertTrue(hay_que_verificar("2026-08-12", HOY))   # 91 días
        self.assertTrue(hay_que_verificar("", HOY))             # sin fecha: no se puede asegurar

    def test_fuentes_usadas_marca_solo_las_viejas(self):
        nuevo = Fragmento("salkantay", "Depósito", "texto", "2026-11-09", ["https://a.com"])
        viejo = Fragmento("lares", "Precio", "texto", "2026-05-01", [])
        usadas = fuentes_usadas([nuevo, viejo], HOY)
        self.assertEqual([u.verificar for u in usadas], [False, True])
        self.assertEqual(usadas[0].dias, 2)
        self.assertEqual(usadas[0].fuentes, ["https://a.com"])


class PruebasFuentes(unittest.TestCase):
    def test_dominios_oficiales(self):
        self.assertTrue(es_oficial("https://www.culturacusco.gob.pe/noticia/x"))
        self.assertTrue(es_oficial("https://busquedas.elperuano.pe/dispositivo/EX/1"))
        self.assertFalse(es_oficial("https://www.salkantaytrekking.com/pdf/a.pdf"))
        self.assertFalse(es_oficial("https://falsogob.pe.example.com/"))

    def test_tabla_tiene_un_renglon_por_archivo_y_cuenta_los_fragmentos(self):
        tabla = tabla_base(CARPETA, HOY)
        self.assertEqual(len(tabla), len(list(CARPETA.glob("*.md"))))
        self.assertEqual(int(tabla["fragmentos"].sum()), len(cargar_fragmentos(CARPETA)))
        self.assertTrue((tabla["actualizado"] != "").all(), "cada archivo debe tener fecha")
        self.assertTrue(tabla["fuentes"].map(len).gt(0).all(), "cada archivo debe tener al menos una fuente")

    def test_buscador(self):
        tabla = tabla_base(CARPETA, HOY)
        lares = list(buscar_en_base(tabla, "LARES")["archivo"])
        self.assertIn("lares", lares)
        self.assertNotIn("salkantay", lares)
        self.assertIn("machu_picchu", list(buscar_en_base(tabla, "elperuano")["archivo"]))  # busca en las fuentes
        self.assertIn("camino_inca", list(buscar_en_base(tabla, "camino inca")["archivo"]))
        self.assertEqual(len(buscar_en_base(tabla, "  ")), len(tabla))
        self.assertTrue(buscar_en_base(tabla, "no-existe-xyz").empty)


class PruebasEstado(unittest.TestCase):
    def test_version_cambia_si_cambia_un_archivo(self):
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = Path(carpeta) / "a.md"
            ruta.write_text("---\nactualizado: 2026-01-02\n---\n\n## Uno\nx\n\n## Dos\ny\n", encoding="utf-8")
            antes = version_base(carpeta)
            self.assertEqual((antes.actualizada, antes.archivos, antes.fragmentos), ("2026-01-02", 1, 2))
            ruta.write_text(ruta.read_text(encoding="utf-8") + "z\n", encoding="utf-8")
            self.assertNotEqual(version_base(carpeta).version, antes.version)

    def test_cuenta_las_pruebas_sin_ejecutarlas(self):
        with tempfile.TemporaryDirectory() as carpeta:
            (Path(carpeta) / "test_a.py").write_text(
                "import sys\nsys.exit(1)\nclass P:\n    def test_x(self): pass\n    def ayuda(self): pass\n"
                "def test_y(): pass\n", encoding="utf-8")
            (Path(carpeta) / "otro.py").write_text("def test_z(): pass\n", encoding="utf-8")
            self.assertEqual(contar_pruebas(carpeta), (2, 1))
        pruebas, archivos = contar_pruebas(RAIZ / "tests")
        self.assertGreater(pruebas, 100)
        self.assertGreaterEqual(archivos, 12)


class PruebasModelos(unittest.TestCase):
    def test_modelos_configurados_leen_el_entorno(self):
        with mock.patch.dict(os.environ, {"GEMINI_MODEL": "m1", "GEMINI_MODEL_RESPALDO": "m2"}):
            self.assertEqual(modelos_configurados("gemini"), ["m1", "m2"])
        with mock.patch.dict(os.environ, {"GEMINI_MODEL": "m1", "GEMINI_MODEL_RESPALDO": ""}):
            self.assertEqual(modelos_configurados("gemini"), ["m1"])
        with mock.patch.dict(os.environ, {"ANTHROPIC_MODEL": "c1"}):
            self.assertEqual(modelos_configurados("claude"), ["c1"])

    def test_la_cuota_restante_solo_se_afirma_cuando_se_sabe(self):
        with mock.patch.dict(os.environ, {"GEMINI_MODEL": "m1"}):
            self.assertIsNone(consultas_restantes("gemini"))
            self.assertIsNone(consultas_restantes("gemini", {"otro"}))
            self.assertEqual(consultas_restantes("gemini", {"m1"}), 0)
        self.assertIn("10 consultas", referencia_cuota("gemini"))
        self.assertIn("pago", referencia_cuota("claude"))


if __name__ == "__main__":
    unittest.main()
