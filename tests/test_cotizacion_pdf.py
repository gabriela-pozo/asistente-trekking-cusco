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
