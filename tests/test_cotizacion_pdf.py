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


def test_genera_pdf_de_una_pagina(ejemplo):
    pdf = generar_cotizacion_pdf(ejemplo)
    assert pdf.startswith(b"%PDF")
    assert len(re.findall(rb"/Type\s*/Page\b", pdf)) == 1


def test_los_montos_coinciden_con_el_resultado(ejemplo):
    texto = texto_pdf(generar_cotizacion_pdf(ejemplo))
    for o in ejemplo["opciones"]:
        op = OpcionCotizada(**o)
        for monto in (op.precio_pp, op.total, op.deposito, op.saldo):
            assert f"US$ {monto}" in texto
    # Latin-1 en el PDF: "ó" se guarda como el byte 0xF3
    assert "Datos de demostración. Confirmar disponibilidad y permisos antes de reservar." in texto


def test_no_aparece_un_monto_ajeno(ejemplo):
    montos = {f"US$ {m}" for o in ejemplo["opciones"] for m in
              (o["precio_pp"], o["precio_pp"] * o["personas"])}
    texto = texto_pdf(generar_cotizacion_pdf(ejemplo))
    assert "US$ 1360" in texto and "US$ 1200" in texto
    assert "US$ 999" not in texto and montos


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
    assert not re.search(r"\+?\d[\d ]{8,}", texto) and "@" not in texto


# ---- El PDF usa el mismo paquete que la respuesta y el panel "Ajustar el paquete" ----------------------------

def _paquete_de_la_app():
    """El paquete que arma la app para el ejemplo guardado (misma selección sugerida que app.py)."""
    from ai.ejemplo import cargar_ejemplo
    from core.cotizacion import cargar_extras, cargar_tarifario
    from core.paquete import Seleccion, armar_paquete, fila_del_trek, noches_sugeridas, sugeridos_validos

    r, _ = cargar_ejemplo()
    tar, ext = cargar_tarifario("data/tarifario_demo.csv"), cargar_extras("data/extras_demo.csv")
    sug = sugeridos_validos(r.perfil.extras_sugeridos, ext, fila_del_trek(r.opciones[0], tar))
    sel = Seleccion(extras=[s.extra_id for s in sug], noches_cusco=noches_sugeridas(r.perfil))
    return r, armar_paquete(r.opciones, tar, ext, sel)


def test_pdf_ejemplo_coincide_con_la_pantalla_y_el_mensaje():
    from ai.pipeline import aplicar_paquete

    r, paquete = _paquete_de_la_app()
    r = aplicar_paquete(r, paquete)
    t = texto_pdf(generar_cotizacion_pdf(r, paquete=paquete))
    mensaje = r.borrador.mensaje_para_cliente
    for monto in ("US$ 1305", "US$ 652.50"):  # total del grupo, por persona y depósito (inglés: punto decimal)
        assert monto in t
        assert monto in mensaje  # mismos montos que la respuesta
    assert paquete.total_c == 130500 and paquete.por_persona_c == 65250 and paquete.deposito_c == 65250
    assert "US$ 600" in t and "US$ 1200" in t           # la línea del trek
    assert "US$ 80" in t and "US$ 25" in t              # hotel (2 × US$ 40) y traslado
    assert "Hotel" not in t or "hotel" in t.lower()


def test_pdf_toma_el_paquete_del_resultado_si_no_se_pasa():
    from ai.pipeline import aplicar_paquete

    r, paquete = _paquete_de_la_app()
    r = aplicar_paquete(r, paquete)
    assert "US$ 1305" in texto_pdf(generar_cotizacion_pdf(r))


def test_incluye_en_el_idioma_del_viajero_y_dias_completos():
    r, paquete = _paquete_de_la_app()
    t = texto_pdf(generar_cotizacion_pdf(r, paquete=paquete, vigencia_dias=7))
    assert "Bilingual guide" in t and "travel insurance" in t   # inglés (el ejemplo es en inglés)
    assert "Guía bilingüe" not in t
    assert "7 days" in t and "7 d)" not in t
    assert "Prepared with Abra Travel" in t


def test_concepto_sin_traduccion_queda_en_el_original():
    from core.cotizacion_pdf import traducir_concepto

    assert traducir_concepto("algo nuevo del tarifario", "en") == "algo nuevo del tarifario"
    assert traducir_concepto("propinas", "pt") == "gorjetas"
    assert traducir_concepto("propinas", "es") == "propinas"


def test_contacto_en_el_pie_si_existe():
    r, paquete = _paquete_de_la_app()
    assert "Contact: +51 900 000 000" in texto_pdf(generar_cotizacion_pdf(r, paquete=paquete, contacto="+51 900 000 000"))
