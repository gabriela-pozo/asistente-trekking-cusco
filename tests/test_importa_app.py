"""Un import roto en app/app.py debe fallar aquí, no en el demo publicado. Sin llamadas a la API.

Correr:  python -m unittest discover tests -v
"""
import ast
import importlib
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "app"))

from recarga import marcar_cargados, recargar_si_cambiaron  # noqa: E402

APP = RAIZ / "app" / "app.py"
DEL_PROYECTO = ("ai", "core", "presentacion", "recarga")


class PruebasImports(unittest.TestCase):
    def test_cada_nombre_importado_en_app_existe(self):
        arbol = ast.parse(APP.read_text(encoding="utf-8"))
        revisados = 0
        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.ImportFrom) and nodo.module and nodo.module.split(".")[0] in DEL_PROYECTO:
                modulo = importlib.import_module(nodo.module)
                for alias in nodo.names:
                    with self.subTest(modulo=nodo.module, nombre=alias.name):
                        self.assertTrue(hasattr(modulo, alias.name), f"{nodo.module} no tiene {alias.name}")
                        revisados += 1
        self.assertGreater(revisados, 30)

    def test_la_app_carga_sin_errores_en_todas_las_paginas(self):
        from streamlit.testing.v1 import AppTest

        with tempfile.TemporaryDirectory() as carpeta, \
                mock.patch.dict(os.environ, {"GEMINI_API_KEY": "", "ABRA_REGISTRO": str(Path(carpeta) / "r.csv")}):
            app = AppTest.from_file(str(APP), default_timeout=60)
            app.run()
            self.assertFalse(app.exception)
            self.assertEqual(app.sidebar.radio[0].options, [
                "Nueva consulta", "Tablero", "Fuentes y verificación", "Mi agencia", "Estado del sistema",
                "Acerca del piloto"])
            for pagina in app.sidebar.radio[0].options:  # antes de la primera consulta (estado vacío)
                app.sidebar.radio[0].set_value(pagina).run()
                self.assertFalse(app.exception, pagina)
            app.sidebar.radio[0].set_value("Nueva consulta").run()
            next(b for b in app.button if b.label == "Usar mensaje de ejemplo").click().run()
            self.assertFalse(app.exception)
            for pagina in [*app.sidebar.radio[0].options, "Nueva consulta"]:
                app.sidebar.radio[0].set_value(pagina).run()
                self.assertFalse(app.exception, pagina)

    def test_fuentes_muestra_los_fragmentos_de_la_ultima_consulta(self):
        from streamlit.testing.v1 import AppTest

        from ai.ejemplo import cargar_ejemplo

        _, datos = cargar_ejemplo()
        with tempfile.TemporaryDirectory() as carpeta,                 mock.patch.dict(os.environ, {"GEMINI_API_KEY": "", "ABRA_REGISTRO": str(Path(carpeta) / "r.csv")}):
            app = AppTest.from_file(str(APP), default_timeout=60)
            app.run()
            next(b for b in app.button if b.label == "Usar mensaje de ejemplo").click().run()
            app.sidebar.radio[0].set_value("Fuentes y verificación").run()
            self.assertFalse(app.exception)
            pagina = " ".join(str(h.proto) for h in app.get("html"))
            for fragmento in datos["fragmentos"]:
                self.assertIn(fragmento["titulo"].split(":")[0], pagina)
            app.text_input(key="buscar_base").input("elperuano").run()
            self.assertTrue(any("de 10 archivos" in c.value for c in app.caption))

    def test_estado_del_sistema_dice_si_se_uso_el_ejemplo(self):
        from streamlit.testing.v1 import AppTest

        with tempfile.TemporaryDirectory() as carpeta,                 mock.patch.dict(os.environ, {"GEMINI_API_KEY": "", "ABRA_REGISTRO": str(Path(carpeta) / "r.csv")}):
            app = AppTest.from_file(str(APP), default_timeout=60)
            app.run()
            app.sidebar.radio[0].set_value("Estado del sistema").run()
            valores = {m.label: m.value for m in app.metric}
            self.assertEqual(valores["Modelo que respondió"], "Sin consulta todavía")
            self.assertEqual(valores["Consultas que quedan hoy"], "No se conoce")
            self.assertGreater(int(valores["Pruebas automáticas"]), 100)
            app.sidebar.radio[0].set_value("Nueva consulta").run()
            next(b for b in app.button if b.label == "Usar mensaje de ejemplo").click().run()
            app.sidebar.radio[0].set_value("Estado del sistema").run()
            self.assertFalse(app.exception)
            valores = {m.label: m.value for m in app.metric}
            self.assertEqual(valores["¿Se usó el ejemplo guardado?"], "Sí")
            self.assertIn("gemini", valores["Modelo que respondió"])
            self.assertTrue(valores["Base de conocimiento"].startswith("v. "))

    def test_acerca_del_piloto_declara_los_limites(self):
        from streamlit.testing.v1 import AppTest

        with mock.patch.dict(os.environ, {"GEMINI_API_KEY": ""}):
            app = AppTest.from_file(str(APP), default_timeout=60)
            app.run()
            app.sidebar.radio[0].set_value("Acerca del piloto").run()
        self.assertFalse(app.exception)
        pagina = " ".join(str(h.proto) for h in app.get("html"))
        for frase in ("datos sintéticos", "ficticia", "17", "No envía mensajes solo", "simulación",
                      "El vendedor siempre revisa"):
            self.assertIn(frase, pagina)


class PruebasRecarga(unittest.TestCase):
    """La caída del demo: app.py nuevo con un ai.pipeline viejo en memoria."""

    def test_un_modulo_viejo_en_memoria_se_vuelve_a_leer(self):
        import ai.pipeline

        real = sys.modules["ai.pipeline"]
        viejo = types.ModuleType("ai.pipeline")  # como el ai.pipeline anterior al paquete
        viejo.__file__ = real.__file__
        viejo.AGENCIA = real.AGENCIA
        try:
            sys.modules["ai.pipeline"] = viejo
            marcar_cargados(RAIZ)
            viejo.__abra_mtime__ = os.path.getmtime(real.__file__) - 60  # se cargó antes del último cambio
            with self.assertRaises(ImportError):  # lo que pasó en Streamlit Cloud
                exec("from ai.pipeline import AGENCIA, aplicar_paquete", {})
            sacados = recargar_si_cambiaron(RAIZ)
            self.assertIn("ai.pipeline", sacados)
            self.assertIn("core.cotizacion", sacados)  # todos juntos, para no mezclar versiones
            exec("from ai.pipeline import AGENCIA, aplicar_paquete", {})  # ahora sí
        finally:
            for nombre in [n for n in sys.modules if n.split(".")[0] in ("ai", "core")]:
                sys.modules.pop(nombre, None)
            importlib.import_module("ai.pipeline")

    def test_sin_cambios_no_saca_nada(self):
        import ai.pipeline  # noqa: F401

        marcar_cargados(RAIZ)
        self.assertEqual(recargar_si_cambiaron(RAIZ), [])


if __name__ == "__main__":
    unittest.main()
