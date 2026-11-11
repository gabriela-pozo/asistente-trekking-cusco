"""Pruebas de core/cotizacion_pdf.py. El texto del PDF se lee sin compresión (pageCompression=0)."""
import json
import re
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

import pytest

from core.cotizacion import OpcionCotizada
from core.cotizacion_pdf import CotizacionPDFError, generar_cotizacion_pdf

RUTA = Path(__file__).resolve().parents[1] / "data" / "ejemplo_guardado.json"


@pytest.fixture
def ejemplo():
    return json.loads(RUTA.read_text(encoding="utf-8"))


def texto_pdf(datos: bytes) -> str:
    """Une los textos literales de los operadores Tj (la fuente WinAnsi guarda ASCII y Latin-1)."""
    crudo = datos.decode("latin-1")
    texto = " ".join(re.findall(r"\(((?:[^()\\]|\\.)*)\)\s*Tj", crudo))
    # reportlab escribe los caracteres no ASCII como escapes octales (\363 = ó) y los paréntesis con barra
    texto = re.sub(r"\\([0-7]{3})", lambda m: chr(int(m.group(1), 8)), texto)
    return re.sub(r"\\([()\\])", r"\1", texto)


def paginas(pdf: bytes) -> int:
    return len(re.findall(rb"/Type\s*/Page\b", pdf))


def con_trek(ejemplo, trek_id: str, idioma: str = "es"):
    """El ejemplo con solo la primera opción, cambiada al trek dado (para probar la sección Ruta)."""
    datos = deepcopy(ejemplo)
    datos["opciones"] = [dict(datos["opciones"][0], trek_id=trek_id)]
    datos["perfil"]["idioma"] = idioma
    return datos


def test_una_pagina_si_el_trek_no_tiene_ruta(ejemplo):
    pdf = generar_cotizacion_pdf(con_trek(ejemplo, "choquequirao_4d"))
    assert pdf.startswith(b"%PDF") and paginas(pdf) == 1
    assert "Ruta:" not in texto_pdf(pdf) and "OpenStreetMap" not in texto_pdf(pdf)
    for sin_ruta in ("inca_jungle_4d", "camino_inca_corto_2d"):
        assert paginas(generar_cotizacion_pdf(con_trek(ejemplo, sin_ruta))) == 1


@pytest.mark.parametrize("trek_id, hitos", [
    ("salkantay_5d", ["Abra Salkantay", "4630 m", "Laguna Humantay", "Aguas Calientes"]),
    ("camino_inca_4d", ["Abra Warmiwa", "4215 m", "Inti Punku", "Machu Picchu"]),
])
def test_pdf_con_ruta_salkantay_y_camino_inca(ejemplo, trek_id, hitos):
    pdf = generar_cotizacion_pdf(con_trek(ejemplo, trek_id))
    texto = texto_pdf(pdf)
    assert pdf.startswith(b"%PDF") and paginas(pdf) == 2
    assert "Ruta:" in texto and "sin dato de altitud" in texto  # hay puntos sin altitud: se marcan
    assert "ruta parcial" not in texto
    assert all(h in texto for h in hitos)
    assert "Referencial: confirmar el recorrido con la agencia" in texto
    assert "\xa9 OpenStreetMap contributors (ODbL)" in texto


def test_lares_se_rotula_ruta_parcial(ejemplo):
    pdf = generar_cotizacion_pdf(con_trek(ejemplo, "lares_4d"))
    texto = texto_pdf(pdf)
    assert paginas(pdf) == 2 and "ruta parcial" in texto and "Pampacorral" in texto
    assert "partial route" in texto_pdf(generar_cotizacion_pdf(con_trek(ejemplo, "lares_4d", "en")))


def test_con_ruta_los_montos_siguen_siendo_los_de_la_pantalla(ejemplo):
    p = paquete_de_pantalla(ejemplo)
    es = dict(ejemplo, perfil=dict(ejemplo["perfil"], idioma="es"))
    pdf = generar_cotizacion_pdf(es, paquete=p)
    texto = texto_pdf(pdf)
    assert paginas(pdf) == 2 and "Ruta:" in texto  # el ejemplo guardado es Salkantay
    assert "US$ 1305" in texto and "US$ 652,50" in texto


def test_ruta_ilegible_no_rompe_el_pdf(ejemplo, monkeypatch):
    from core import mapa

    def falla(*_a, **_k):
        raise OSError("sin disco")
    monkeypatch.setattr(mapa, "cargar_ruta", falla)
    pdf = generar_cotizacion_pdf(ejemplo)
    assert pdf.startswith(b"%PDF") and paginas(pdf) == 1


def paquete_de_pantalla(ejemplo):
    """El paquete que arma la app para el ejemplo guardado: seleccion_sugerida (sin extras del modelo y 1 noche
    en Cusco porque no dice cuándo llega) con armar_paquete, el mismo código de core que usa la pantalla."""
    from core.cotizacion import cargar_extras, cargar_tarifario
    from core.paquete import Seleccion, armar_paquete, noches_sugeridas
    raiz = RUTA.parent
    opciones = [OpcionCotizada(**o) for o in ejemplo["opciones"]]
    perfil = type("P", (), ejemplo["perfil"])
    sel = Seleccion(extras=[], noches_cusco=noches_sugeridas(perfil))
    return armar_paquete(opciones, cargar_tarifario(raiz / "tarifario_demo.csv"),
                         cargar_extras(raiz / "extras_demo.csv"), sel)


def test_el_total_del_pdf_es_el_de_la_pantalla(ejemplo):
    p = paquete_de_pantalla(ejemplo)
    # La pantalla muestra US$ 1305 en total y US$ 652,50 por persona (trek 1200 + hotel 80 + traslado 25)
    assert (p.total_c, p.por_persona_c, p.deposito_c, p.saldo_c) == (130500, 65250, 65250, 65250)
    es = dict(ejemplo, perfil=dict(ejemplo["perfil"], idioma="es"))
    texto = texto_pdf(generar_cotizacion_pdf(es, paquete=p))
    assert "US$ 1305" in texto and "US$ 652,50" in texto
    assert "US$ 1200" in texto and "US$ 80" in texto and "US$ 25" in texto  # una fila por línea
    en = texto_pdf(generar_cotizacion_pdf(ejemplo, paquete=p))  # el ejemplo está en inglés: punto decimal
    assert "US$ 1305" in en and "US$ 652.50" in en


def test_el_pdf_usa_resultado_paquete_si_existe(ejemplo):
    class R:  # lo que tiene el Resultado del pipeline
        pass
    r = R()
    r.perfil, r.opciones, r.paquete = ejemplo["perfil"], [OpcionCotizada(**o) for o in ejemplo["opciones"]], paquete_de_pantalla(ejemplo)
    assert "US$ 1305" in texto_pdf(generar_cotizacion_pdf(r))


def test_con_recargo_el_total_es_el_del_paquete(ejemplo):
    from dataclasses import replace
    p = replace(paquete_de_pantalla(ejemplo), metodo_pago="tarjeta", porcentaje_recargo=5.0)
    texto = texto_pdf(generar_cotizacion_pdf(ejemplo, paquete=p))
    assert f"US$ {p.total_c / 100:g}" in texto and "US$ 65.25" in texto  # recargo 5 % de 1305


def test_aviso_de_demostracion(ejemplo):
    texto = texto_pdf(generar_cotizacion_pdf(ejemplo))
    assert "Datos de demostración. Confirmar disponibilidad y permisos antes de reservar." in texto


def test_incluye_en_el_idioma_del_viajero(ejemplo):
    en = texto_pdf(generar_cotizacion_pdf(ejemplo))
    assert "bilingual guide" in en and "travel insurance" in en and "Guía" not in en
    ejemplo["perfil"]["idioma"] = "pt"
    pt = texto_pdf(generar_cotizacion_pdf(ejemplo))
    assert "seguro de viagem" in pt
    ejemplo["opciones"][0]["incluye"] = ["concepto nuevo del tarifario"]
    assert "concepto nuevo del tarifario" in texto_pdf(generar_cotizacion_pdf(ejemplo))  # sin traducción: el original


def test_vigencia_en_palabras_y_pie(ejemplo):
    texto = texto_pdf(generar_cotizacion_pdf(ejemplo))
    assert "7 days" in texto and "7 d (" not in texto
    assert "Prepared with Abra Travel" in texto and "+51" not in texto
    con = texto_pdf(generar_cotizacion_pdf(ejemplo, contacto="agencia@ejemplo.pe"))
    assert "Prepared with Abra Travel · agencia@ejemplo.pe" in con


@pytest.mark.parametrize("idioma", ["pt", "en", "es", "fr"])
def test_idiomas(ejemplo, idioma):
    ejemplo["perfil"]["idioma"] = idioma
    assert generar_cotizacion_pdf(ejemplo).startswith(b"%PDF")


def test_fecha_en_reloj_de_lima(ejemplo):
    # 02:00 UTC del 11/11 sigue siendo el 10/11 en Lima (UTC-5)
    ahora = datetime(2026, 11, 11, 2, 0, tzinfo=timezone.utc)
    ejemplo["perfil"]["idioma"] = "es"
    ejemplo["perfil"]["idioma"] = "es"
    assert "10 de noviembre de 2026" in texto_pdf(generar_cotizacion_pdf(ejemplo, ahora=ahora))


def test_vigencia_es_parametro(ejemplo):
    ahora = datetime(2026, 11, 10, 15, 0, tzinfo=timezone.utc)
    ejemplo["perfil"]["idioma"] = "es"
    ejemplo["perfil"]["idioma"] = "es"
    assert "17 de noviembre de 2026" in texto_pdf(generar_cotizacion_pdf(ejemplo, ahora=ahora))
    assert "20 de noviembre de 2026" in texto_pdf(generar_cotizacion_pdf(ejemplo, vigencia_dias=10, ahora=ahora))


@pytest.mark.parametrize("quitar, mensaje", [
    (("perfil",), "perfil"),
    (("perfil", "idioma"), "perfil.idioma"),
    (("opciones",), "opciones"),
    (("opciones", 0, "precio_pp"), "opciones[0].precio_pp"),
])
def test_falla_con_mensaje_claro_si_falta_un_campo(ejemplo, quitar, mensaje):
    datos = deepcopy(ejemplo)
    objeto = datos
    for k in quitar[:-1]:
        objeto = objeto[k]
    del objeto[quitar[-1]]
    with pytest.raises(CotizacionPDFError, match=mensaje.replace("[", r"\[").replace("]", r"\]")):
        generar_cotizacion_pdf(datos)


def test_sin_datos_personales(ejemplo):
    texto = texto_pdf(generar_cotizacion_pdf(ejemplo))
    assert not re.search(r"\+?\d{9,}", texto) and "@" not in texto
