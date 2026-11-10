"""Pruebas de la base de conocimiento y la búsqueda. No llaman a ninguna API.

Correr:  python -m unittest discover tests -v
"""
import re
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from ai.knowledge import (  # noqa: E402
    BaseConocimiento, archivos_desde_perfil, consulta_desde_perfil, leer_cabecera,
)

CARPETA = RAIZ / "data" / "knowledge"
BASE = BaseConocimiento(CARPETA)


def perfil(**datos):
    base = dict(treks_de_interes=[], temas_consulta=[], mes_viaje=None)
    base.update(datos)
    return SimpleNamespace(**base)


def buscar_por_perfil(p, k=6):
    return BASE.buscar(consulta_desde_perfil(p), k=k, archivos_prioritarios=archivos_desde_perfil(p))


class PruebasFragmentos(unittest.TestCase):
    def test_un_fragmento_por_seccion(self):
        secciones = sum(r.read_text(encoding="utf-8").count("\n## ") for r in CARPETA.glob("*.md"))
        self.assertEqual(len(BASE.fragmentos), secciones)
        self.assertEqual(len(BASE.fragmentos), 48)  # 10 archivos: 28 secciones + 4 treks nuevos x 5

    def test_cada_fragmento_tiene_fecha_fuentes_y_texto(self):
        for f in BASE.fragmentos:
            self.assertRegex(f.actualizado, r"^\d{4}-\d{2}-\d{2}$", f.titulo)
            self.assertTrue(f.fuentes and all(u.startswith("http") for u in f.fuentes), f.titulo)
            self.assertTrue(f.texto, f.titulo)
            self.assertNotIn("##", f.texto, f.titulo)

    def test_cada_archivo_tiene_fecha_y_fuente(self):
        archivos = sorted(CARPETA.glob("*.md"))
        self.assertEqual(len(archivos), 10)
        for ruta in archivos:
            meta, _ = leer_cabecera(ruta.read_text(encoding="utf-8"))
            self.assertRegex(meta.get("actualizado", ""), r"^\d{4}-\d{2}-\d{2}$", ruta.name)
            fuentes = meta.get("fuentes") or []
            self.assertTrue(fuentes and all(u.startswith("http") for u in fuentes), ruta.name)

    def test_cabecera_no_entra_al_texto(self):
        # Ninguna línea del texto debe ser una clave de la cabecera ("tema:", "fuentes:", ...).
        cabecera = re.compile(r"^(tema|actualizado|fuentes|estado):", re.MULTILINE)
        self.assertTrue(all(not cabecera.search(f.texto) for f in BASE.fragmentos))

    def test_leer_cabecera(self):
        meta, cuerpo = leer_cabecera("---\ntema: X\nactualizado: 2026-01-01\nfuentes:\n  - https://a\n  - https://b\n---\n## T\nhola")
        self.assertEqual(meta["actualizado"], "2026-01-01")
        self.assertEqual(meta["fuentes"], ["https://a", "https://b"])
        self.assertIn("## T", cuerpo)

    def test_para_prompt_lleva_origen_y_fecha(self):
        texto = BASE.fragmentos[0].para_prompt()
        self.assertIn("actualizado 2026-11-09", texto)


class PruebasBusqueda(unittest.TestCase):
    def test_encuentra_lo_mas_parecido(self):
        primero = BASE.buscar("permisos no reembolsables", k=1)[0]
        self.assertEqual(primero.titulo, "Permisos del Camino Inca: no reembolsables")

    def test_acentos_no_importan(self):
        con = [f.titulo for f in BASE.buscar("aclimatación altura", k=3)]
        sin = [f.titulo for f in BASE.buscar("aclimatacion altura", k=3)]
        self.assertEqual(con, sin)

    def test_en_ingles_casi_no_encuentra_nada(self):
        """Por esto la búsqueda se arma en español desde el perfil."""
        self.assertEqual(max(BASE.puntajes("sleeping bag rental cancellation policy")), 0.0)
        self.assertGreater(max(BASE.puntajes("bolsa de dormir cancelaciones")), 0.1)

    def test_respeta_k_y_no_repite(self):
        resultado = BASE.buscar("salkantay camino inca machu picchu", k=4)
        self.assertEqual(len(resultado), 4)
        self.assertEqual(len({(f.archivo, f.titulo) for f in resultado}), 4)

    def test_prioritarios_entran_aunque_no_se_parezcan(self):
        resultado = BASE.buscar("altura aclimatación", k=6, archivos_prioritarios=["salkantay", "condiciones_reserva"])
        archivos = [f.archivo for f in resultado]
        self.assertGreaterEqual(archivos.count("salkantay"), 2)
        self.assertEqual(archivos.count("condiciones_reserva"), 2)  # no habla de altura: entra solo por la garantía
        self.assertIn("altura_y_preparacion", archivos)  # lo que sí pidió también entra


class PruebasPerfil(unittest.TestCase):
    def test_siempre_incluye_trek_pedido_y_reserva(self):
        for trek, archivo in (("salkantay", "salkantay"), ("camino_inca", "camino_inca")):
            archivos = {f.archivo for f in buscar_por_perfil(perfil(treks_de_interes=[trek], temas_consulta=["altura"]))}
            self.assertIn(archivo, archivos)
            self.assertIn("condiciones_reserva", archivos)

    def test_sin_trek_igual_incluye_reserva(self):
        archivos = {f.archivo for f in buscar_por_perfil(perfil(temas_consulta=["entrada a Machu Picchu"]))}
        self.assertIn("condiciones_reserva", archivos)
        self.assertIn("machu_picchu", archivos)

    def test_salkantay_en_marzo_trae_lluvias(self):
        p = perfil(treks_de_interes=["salkantay"], mes_viaje=3, temas_consulta=["qué incluye"])
        archivos = {f.archivo for f in buscar_por_perfil(p)}
        self.assertIn("altura_y_preparacion", archivos)  # temporada de lluvias

    def test_camino_inca_en_febrero_trae_cierre_y_salkantay(self):
        p = perfil(treks_de_interes=["camino_inca"], mes_viaje=2)
        self.assertEqual(archivos_desde_perfil(p), ["camino_inca", "salkantay", "condiciones_reserva"])
        titulos = [f.titulo for f in buscar_por_perfil(p)]
        self.assertIn("Camino Inca: cierre anual en febrero", titulos)
        self.assertTrue(any(t.startswith("Salkantay") for t in titulos))

    def test_consulta_esta_en_espanol(self):
        consulta = consulta_desde_perfil(perfil(treks_de_interes=["camino_inca"], temas_consulta=["precio"], mes_viaje=11))
        self.assertIn("camino inca", consulta)
        self.assertIn("temporada de lluvias", consulta)
        self.assertIn("depósito", consulta)


if __name__ == "__main__":
    unittest.main()
