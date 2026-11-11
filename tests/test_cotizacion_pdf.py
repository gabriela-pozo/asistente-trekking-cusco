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


def con_trek(ejemplo: dict, ruta: str) -> dict:
    """El ejemplo guardado con otro trek (solo cambia el id; los montos no se tocan)."""
    d = deepcopy(ejemplo)
    for o in d["opciones"]:
        o["trek_id"] = f"{ruta}_4d"
    return d


def test_genera_pdf_con_pagina_de_ruta_para_salkantay(ejemplo):
    pdf = generar_cotizacion_pdf(ejemplo)
    assert pdf.startswith(b"%PDF")
    assert paginas(pdf) == 2  # cotización + ruta
    t = texto_pdf(pdf)
    assert "Route: " in t and "Altitude profile" in t and "Route points" in t
    assert "OpenStreetMap" in t and "ODbL" in t
    assert "confirm the route with the agency" in t
    assert "partial route" not in t


def test_camino_inca_tiene_ruta(ejemplo):
    pdf = generar_cotizacion_pdf(con_trek(ejemplo, "camino_inca"))
    assert pdf.startswith(b"%PDF") and paginas(pdf) == 2
    assert "Altitude profile" in texto_pdf(pdf)


@pytest.mark.parametrize("ruta", ["choquequirao", "inca_jungle", "camino_inca_corto"])
def test_trek_sin_ruta_sigue_en_una_pagina(ejemplo, ruta):
    pdf = generar_cotizacion_pdf(con_trek(ejemplo, ruta))
    assert pdf.startswith(b"%PDF") and paginas(pdf) == 1
    assert "Altitude profile" not in texto_pdf(pdf)


def test_lares_dice_ruta_parcial(ejemplo):
    pdf = generar_cotizacion_pdf(con_trek(ejemplo, "lares"))
    assert paginas(pdf) == 2
    assert "partial route" in texto_pdf(pdf)


def test_la_ruta_solo_usa_puntos_de_data_rutas(ejemplo):
    from core.mapa import cargar_ruta

    t = texto_pdf(generar_cotizacion_pdf(ejemplo))
    for p in cargar_ruta("salkantay").puntos:
        assert p.lugar in t
        if p.altitud_m is not None:
            assert f"{p.altitud_m:,} m".replace(",", " ") in t
    assert "no data" in t  # los puntos sin altitud se marcan, no se inventan


def test_los_montos_coinciden_con_el_resultado(ejemplo):
    ejemplo = deepcopy(ejemplo)
    ejemplo["perfil"]["idioma"] = "es"  # el aviso en español, en un PDF en español
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
    assert not re.search(r"\+?\d{3}[\d ]{6,}", texto) and "@" not in texto


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


# ---- Revisión del PDF del ejemplo (símbolos, itinerario de referencia, aviso traducido, km) --------------------

def en_idioma(ejemplo: dict, idioma: str) -> dict:
    d = deepcopy(ejemplo)
    d["perfil"]["idioma"] = idioma
    return d


@pytest.mark.parametrize("idioma,hotel", [("en", "3-star hotel"), ("es", "hotel de 3 estrellas"),
                                          ("pt", "hotel 3 estrelas")])
def test_la_estrella_sale_como_texto_en_el_pdf(idioma, hotel):
    from ai.pipeline import aplicar_paquete

    r, paquete = _paquete_de_la_app()
    r.perfil.idioma = idioma
    res = aplicar_paquete(r, paquete)
    t = texto_pdf(generar_cotizacion_pdf(res, paquete=paquete))
    assert "★" not in t and hotel in t
    assert "★" in res.borrador.mensaje_para_cliente  # el mensaje de WhatsApp no se toca


def test_ningun_texto_del_pdf_sale_de_winansi():
    """Helvetica solo trae WinAnsi: todo lo que se dibuja pasa por _limpio y cabe en cp1252."""
    import csv

    from core.cotizacion_pdf import CONCEPTOS, TEXTOS, _limpio
    from core.mapa import CARPETA_RUTAS

    textos = [v for idi in TEXTOS.values() for v in idi.values() if isinstance(v, str)]
    textos += [x for c in CONCEPTOS.values() for x in c.values()]
    for archivo in CARPETA_RUTAS.glob("*.csv"):
        textos += [f["lugar"] for f in csv.DictReader(archivo.open(encoding="utf-8"))]
    for extra in csv.DictReader(open("data/extras_demo.csv", encoding="utf-8")):
        textos += [extra["extra"], extra.get("beneficio_para_el_viajero", "")]
    for idioma in ("es", "en", "pt"):
        for t in textos + ["hotel 3★ en Cusco", "4★", "★ → ≈ – “x”"]:
            _limpio(t, idioma).encode("cp1252")  # no lanza
    assert "★" not in _limpio("hotel 4★", "es")


def test_itinerario_de_referencia_de_5_dias_para_una_cotizacion_de_4(ejemplo):
    t = texto_pdf(generar_cotizacion_pdf(ejemplo))
    assert "reference itinerary of 5 days" in t
    assert "Your quote is for 4 days: the agency will confirm how the quoted option is organised" in t
    es = texto_pdf(generar_cotizacion_pdf(en_idioma(ejemplo, "es")))
    assert "itinerario de referencia de 5 días" in es and "la agencia confirmará cómo se organiza" in es


def test_perfil_de_altitud_con_marcas_de_km(ejemplo):
    t = texto_pdf(generar_cotizacion_pdf(ejemplo))
    assert " km " in f" {t} " and "50" in t  # el eje horizontal tiene marcas y la unidad


def test_las_etiquetas_del_mapa_no_se_pisan():
    from core.cotizacion_pdf import _colocar_etiquetas
    from core.mapa import cargar_ruta

    ruta = cargar_ruta("salkantay")
    xy = [(100 + i * 12, 50 + i * 6) for i in range(len(ruta.puntos))]  # puntos muy juntos
    nombres = [f"{i + 1}. {p.lugar}" for i, p in enumerate(ruta.puntos)]
    pos = _colocar_etiquetas(xy, nombres, 510, 280)
    cajas = []
    for (tx, ty, ancla, _), nombre in zip(pos, nombres):
        w = len(nombre) * 6.8 * 0.52 + 2
        x0 = tx if ancla == "start" else tx - w
        cajas.append((x0, ty, x0 + w, ty + 6.8))
    for i, a in enumerate(cajas):
        for b in cajas[i + 1:]:
            assert a[2] < b[0] or a[0] > b[2] or a[3] < b[1] or a[1] > b[3]


@pytest.mark.parametrize("idioma,aviso", [
    ("es", "Datos de demostración. Confirmar disponibilidad y permisos antes de reservar."),
    ("en", "Demo data. Confirm availability and permits before booking."),
    ("pt", "Dados de demonstração. Confirmar disponibilidade e permissões antes de reservar.")])
def test_aviso_de_demostracion_en_el_idioma_del_pdf(ejemplo, idioma, aviso):
    assert aviso in texto_pdf(generar_cotizacion_pdf(en_idioma(ejemplo, idioma)))
