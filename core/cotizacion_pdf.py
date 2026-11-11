"""Cotización en PDF (A4, una página) a partir del resultado de una consulta.

    generar_cotizacion_pdf(resultado) -> bytes

`resultado` puede ser el `Resultado` de ai/pipeline.py o el dict de data/ejemplo_guardado.json.
Los montos NO se calculan aquí: salen de `OpcionCotizada` (precio_pp, total, deposito, saldo),
el mismo código que cotiza para el mensaje de WhatsApp. Este módulo no importa nada de ai/ ni de app/.

Se usa la fuente Helvetica de reportlab (codificación WinAnsi): trae tildes y ñ sin archivos de fuente.
Colores: paleta "Abra: del glaciar al amanecer" (docs/diseno.md), con fondo blanco para imprimir.
"""
from __future__ import annotations

import io
from datetime import date, datetime, timezone
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import KeepInFrame, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from core.cotizacion import NOMBRE_NIVEL, OpcionCotizada

AGENCIA_POR_DEFECTO = "Abra Travel"
VIGENCIA_DIAS_POR_DEFECTO = 7  # SUPUESTO: la agencia no fija una vigencia; se marca como tal en el PDF.

# Paleta (docs/diseno.md)
CUMBRE = colors.HexColor("#0B2E3A")
LAGUNA = colors.HexColor("#0B6E7F")
AMANECER = colors.HexColor("#F59E2E")
TIERRA = colors.HexColor("#B45F06")
BORDE = colors.HexColor("#DDD6C8")
TINTA = colors.HexColor("#12303A")
SECUNDARIO = colors.HexColor("#4A5F66")
AVISO_FONDO = colors.HexColor("#FFF1D6")
AVISO_TEXTO = colors.HexColor("#7A4B00")

AVISO_DEMO = "Datos de demostración. Confirmar disponibilidad y permisos antes de reservar."

MESES = {
    "es": ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
           "noviembre", "diciembre"],
    "en": ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
           "November", "December"],
    "pt": ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro",
           "novembro", "dezembro"],
}

# Texto breve en el idioma del viajero. Idiomas sin traducción caen en inglés.
TEXTOS = {
    "es": {
        "saludo": "Gracias por tu consulta. Esta es la cotización que preparamos para ti.",
        "tus_datos": "Lo que entendimos de tu consulta",
        "opciones": "Opciones",
        "incluye": "Incluye", "no_incluye": "No incluye",
        "cols": ["Trek", "Días", "Nivel", "Por persona", "Total", "Depósito", "Saldo"],
        "grupo": "Grupo", "personas": "persona(s)", "fechas": "Fechas", "idioma": "Idioma", "sin_dato": "por confirmar",
        "nota_saldo": "El depósito reserva el cupo; el saldo se paga hasta 30 días antes del trek.",
        "permiso": "Requiere permiso del Camino Inca: verificar disponibilidad antes de confirmar.",
        "emision": "Emitida el", "vigencia": "Vigencia", "supuesto": "supuesto",
        "hasta": "hasta el", "alt": "Alternativa", "moneda": "Precios en dólares (US$).",
    },
    "en": {
        "saludo": "Thank you for your enquiry. Here is the quote we prepared for you.",
        "tus_datos": "What we understood from your enquiry",
        "opciones": "Options",
        "incluye": "Included", "no_incluye": "Not included",
        "cols": ["Trek", "Days", "Level", "Per person", "Total", "Deposit", "Balance"],
        "grupo": "Group", "personas": "traveller(s)", "fechas": "Dates", "idioma": "Language", "sin_dato": "to be confirmed",
        "nota_saldo": "The deposit holds your spot; the balance is due up to 30 days before the trek.",
        "permiso": "Inca Trail permit required: availability must be checked before confirming.",
        "emision": "Issued on", "vigencia": "Valid", "supuesto": "assumption",
        "hasta": "until", "alt": "Alternative", "moneda": "Prices in US dollars (US$).",
    },
    "pt": {
        "saludo": "Obrigado pela sua consulta. Esta é a cotação que preparamos para você.",
        "tus_datos": "O que entendemos da sua consulta",
        "opciones": "Opções",
        "incluye": "Inclui", "no_incluye": "Não inclui",
        "cols": ["Trilha", "Dias", "Nível", "Por pessoa", "Total", "Entrada", "Saldo"],
        "grupo": "Grupo", "personas": "pessoa(s)", "fechas": "Datas", "idioma": "Idioma", "sin_dato": "a confirmar",
        "nota_saldo": "A entrada garante a vaga; o saldo é pago até 30 dias antes da trilha.",
        "permiso": "Exige permissão da Trilha Inca: verificar disponibilidade antes de confirmar.",
        "emision": "Emitida em", "vigencia": "Validade", "supuesto": "suposição",
        "hasta": "até", "alt": "Alternativa", "moneda": "Preços em dólares (US$).",
    },
}
NOMBRE_IDIOMA = {"es": "Español", "en": "English", "pt": "Português"}
NIVEL_TXT = {
    "es": NOMBRE_NIVEL,
    "en": {"economico": "budget", "estandar": "standard", "premium": "premium"},
    "pt": {"economico": "econômico", "estandar": "padrão", "premium": "premium"},
}


class CotizacionPDFError(ValueError):
    """Falta un campo del resultado o es inválido: el mensaje dice cuál."""


def _campo(obj, nombre: str, contexto: str, obligatorio: bool = True):
    """Lee `nombre` de un dict o de un objeto; falla con un mensaje claro si es obligatorio y no está."""
    if isinstance(obj, dict):
        valor = obj.get(nombre)
        existe = nombre in obj
    else:
        valor = getattr(obj, nombre, None)
        existe = hasattr(obj, nombre)
    if obligatorio and (not existe or valor is None):
        raise CotizacionPDFError(f"No se puede generar la cotización: falta el campo '{contexto}{nombre}'.")
    return valor


def _opciones(resultado) -> list[OpcionCotizada]:
    crudas = _campo(resultado, "opciones", "")
    if not crudas:
        raise CotizacionPDFError("No se puede generar la cotización: 'opciones' está vacío.")
    salida = []
    for i, o in enumerate(crudas):
        if isinstance(o, OpcionCotizada):
            salida.append(o)
            continue
        for campo in ("trek", "dias", "nivel", "precio_pp", "personas"):
            _campo(o, campo, f"opciones[{i}].")
        try:  # "extras" venía en ejemplos guardados antiguos
            salida.append(OpcionCotizada(**{k: v for k, v in o.items() if k != "extras"}))
        except TypeError as e:
            raise CotizacionPDFError(f"No se puede generar la cotización: opciones[{i}] no es válida ({e}).") from e
    return salida


def _fecha_texto(dia: date, idioma: str) -> str:
    meses = MESES.get(idioma, MESES["en"])
    if idioma == "en":
        return f"{meses[dia.month - 1]} {dia.day}, {dia.year}"
    de = " de " if idioma == "es" else " de "
    return f"{dia.day}{de}{meses[dia.month - 1]}{de}{dia.year}"


def _hoy_lima(ahora: datetime | None) -> date:
    from datetime import timedelta
    try:
        from zoneinfo import ZoneInfo
        zona = ZoneInfo("America/Lima")
    except Exception:  # noqa: BLE001 - Windows sin tzdata; Perú no usa horario de verano
        zona = timezone(timedelta(hours=-5))
    return (ahora or datetime.now(timezone.utc)).astimezone(zona).date()


def _usd(n: int) -> str:
    return f"US$ {n}"  # mismo formato que OpcionCotizada.resumen(): sin separador de miles


def _p(texto: str, estilo: ParagraphStyle) -> Paragraph:
    return Paragraph(escape(str(texto)), estilo)


def generar_cotizacion_pdf(resultado, *, agencia: str = AGENCIA_POR_DEFECTO,
                           vigencia_dias: int = VIGENCIA_DIAS_POR_DEFECTO,
                           ahora: datetime | None = None) -> bytes:
    """Devuelve los bytes de un PDF A4 de una página. `ahora` fija el reloj en las pruebas."""
    perfil = _campo(resultado, "perfil", "")
    idioma = str(_campo(perfil, "idioma", "perfil.")).lower()[:2]
    opciones = _opciones(resultado)
    t = TEXTOS.get(idioma, TEXTOS["en"])
    nivel_txt = NIVEL_TXT.get(idioma, NIVEL_TXT["en"])

    hoy = _hoy_lima(ahora)
    vence = date.fromordinal(hoy.toordinal() + int(vigencia_dias))

    base = ParagraphStyle("base", fontName="Helvetica", fontSize=9, leading=12, textColor=TINTA, alignment=TA_LEFT)
    peq = ParagraphStyle("peq", parent=base, fontSize=8, leading=10.5, textColor=SECUNDARIO)
    h2 = ParagraphStyle("h2", parent=base, fontName="Helvetica-Bold", fontSize=11, leading=14, textColor=LAGUNA,
                        spaceBefore=8, spaceAfter=3)
    th = ParagraphStyle("th", parent=base, fontName="Helvetica-Bold", fontSize=8, textColor=colors.white)
    tdr = ParagraphStyle("tdr", parent=base, alignment=2)
    tdrb = ParagraphStyle("tdrb", parent=tdr, fontName="Helvetica-Bold", textColor=TIERRA)
    thr = ParagraphStyle("thr", parent=th, alignment=2)

    hist = []

    # Encabezado: barra Cumbre con el nombre y la fecha de emisión (franja Amanecer debajo)
    cab = ParagraphStyle("cab", parent=base, fontName="Helvetica-Bold", fontSize=18, leading=22, textColor=colors.white)
    cab2 = ParagraphStyle("cab2", parent=base, fontSize=9, textColor=colors.HexColor("#E6F1F3"), alignment=2)
    enc = Table([[_p(agencia, cab), _p(f"{t['emision']} {_fecha_texto(hoy, idioma)}", cab2)]], colWidths=[100 * mm, 80 * mm])
    enc.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), CUMBRE), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                             ("LINEBELOW", (0, 0), (-1, -1), 3, AMANECER),
                             ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                             ("TOPPADDING", (0, 0), (-1, -1), 9), ("BOTTOMPADDING", (0, 0), (-1, -1), 9)]))
    hist += [enc, Spacer(1, 6), _p(t["saludo"], base)]

    # Datos entendidos
    personas = _campo(perfil, "num_personas", "perfil.", obligatorio=False) or opciones[0].personas
    fechas = _campo(perfil, "fecha_texto", "perfil.", obligatorio=False)
    if not fechas:
        mes = _campo(perfil, "mes_viaje", "perfil.", obligatorio=False)
        fechas = MESES.get(idioma, MESES["en"])[int(mes) - 1] if mes else t["sin_dato"]
    treks = ", ".join(sorted({o.trek for o in opciones}))
    datos = [
        [_p(t["grupo"], peq), _p(f"{personas} {t['personas']}", base), _p(t["fechas"], peq), _p(fechas, base)],
        [_p("Trek", peq), _p(treks, base), _p(t["idioma"], peq), _p(NOMBRE_IDIOMA.get(idioma, idioma), base)],
    ]
    tb = Table(datos, colWidths=[22 * mm, 68 * mm, 22 * mm, 68 * mm])
    tb.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.6, BORDE), ("INNERGRID", (0, 0), (-1, -1), 0.3, BORDE),
                            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                            ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
    hist += [_p(t["tus_datos"], h2), tb]

    # Tabla de opciones (montos tal como los da OpcionCotizada)
    filas = [[_p(c, thr if i >= 3 else th) for i, c in enumerate(t["cols"])]]
    for o in opciones:
        nombre = o.trek + (f" ({t['alt']})" if o.es_alternativa else "")
        filas.append([_p(nombre, base), _p(str(o.dias), base), _p(nivel_txt.get(o.nivel, o.nivel), base),
                      _p(_usd(o.precio_pp), tdr), _p(_usd(o.total), tdrb), _p(_usd(o.deposito), tdr),
                      _p(_usd(o.saldo), tdr)])
    tab = Table(filas, colWidths=[48 * mm, 12 * mm, 20 * mm, 26 * mm, 26 * mm, 24 * mm, 24 * mm], repeatRows=1)
    tab.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), LAGUNA),
                             ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F5F1E8")]),
                             ("BOX", (0, 0), (-1, -1), 0.6, BORDE), ("INNERGRID", (0, 0), (-1, -1), 0.3, BORDE),
                             ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                             ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
    hist += [_p(t["opciones"], h2), tab, Spacer(1, 3), _p(f"{t['moneda']} {t['nota_saldo']}", peq)]
    if any(o.requiere_permiso for o in opciones):
        hist += [_p(t["permiso"], peq)]

    # Qué incluye y qué no (del tarifario; las listas vienen en español)
    ref = opciones[0]
    incl = Table([[_p(t["incluye"], ParagraphStyle("hi", parent=base, fontName="Helvetica-Bold", textColor=LAGUNA)),
                   _p(t["no_incluye"], ParagraphStyle("hn", parent=base, fontName="Helvetica-Bold", textColor=TIERRA))],
                  [_p("; ".join(ref.incluye), base), _p("; ".join(ref.no_incluye), base)]],
                 colWidths=[90 * mm, 90 * mm])
    incl.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
    hist += [Spacer(1, 6), incl]

    # Vigencia (supuesto)
    hist += [Spacer(1, 6),
             _p(f"{t['vigencia']}: {vigencia_dias} d ({t['hasta']} {_fecha_texto(vence, idioma)}) — {t['supuesto']}.", peq)]

    # Aviso de demostración, visible
    aviso = ParagraphStyle("aviso", parent=base, fontName="Helvetica-Bold", textColor=AVISO_TEXTO)
    av = Table([[_p(AVISO_DEMO, aviso)]], colWidths=[180 * mm])
    av.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), AVISO_FONDO), ("BOX", (0, 0), (-1, -1), 0.8, AMANECER),
                            ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                            ("LEFTPADDING", (0, 0), (-1, -1), 8)]))
    hist += [Spacer(1, 10), av]

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm, topMargin=15 * mm,
                            bottomMargin=15 * mm, title=f"{agencia}: cotización", author=agencia,
                            pageCompression=0)
    marco = A4[0] - 30 * mm, A4[1] - 30 * mm
    # KeepInFrame reduce si algo no cabe: la cotización siempre queda en una sola página
    doc.build([KeepInFrame(marco[0], marco[1], hist, mode="shrink")])
    return buf.getvalue()
