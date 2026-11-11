"""Cotización en PDF (A4; una página, y una segunda con la ruta si el trek tiene datos) a partir del resultado de una consulta.

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
from reportlab.graphics.shapes import Circle, Drawing, Line, PolyLine, String
from reportlab.platypus import (KeepInFrame, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

from core import mapa
from core.cotizacion import NOMBRE_NIVEL, OpcionCotizada
from core.paquete import HOTEL, METODOS, Paquete, _nombre_y_beneficio, monto
from core.respuesta_nocturna import _POSICION, INCLUYE, nombre_trek

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


FRASES_PAQUETE = {
    "es": {"cols": ["Concepto", "Detalle", "Importe"], "dias": "días", "dias_vig": "días", "noche": "noche",
           "noche_s": "noches", "grupo": "grupo", "total": "Total", "por_persona": "Total por persona",
           "deposito": "Depósito (50 %)", "saldo": "Saldo", "recargo": "Recargo por forma de pago",
           "otra": "Otra opción", "pp": "por persona", "solo_trek": "solo el trek", "preparado": "Preparado con"},
    "en": {"cols": ["Item", "Detail", "Amount"], "dias": "days", "dias_vig": "days", "noche": "night",
           "noche_s": "nights", "grupo": "group", "total": "Total", "por_persona": "Total per person",
           "deposito": "Deposit (50 %)", "saldo": "Balance", "recargo": "Payment method surcharge",
           "otra": "Another option", "pp": "per person", "solo_trek": "trek only", "preparado": "Prepared with"},
    "pt": {"cols": ["Item", "Detalhe", "Valor"], "dias": "dias", "dias_vig": "dias", "noche": "noite",
           "noche_s": "noites", "grupo": "grupo", "total": "Total", "por_persona": "Total por pessoa",
           "deposito": "Entrada (50 %)", "saldo": "Saldo", "recargo": "Acréscimo pela forma de pagamento",
           "otra": "Outra opção", "pp": "por pessoa", "solo_trek": "só a trilha", "preparado": "Preparado com"},
}
# Conceptos del tarifario que respuesta_nocturna.INCLUYE no trae (sobre todo los de "no incluye"). Claves en minúscula.
# Si un concepto no está en ninguno de los dos diccionarios, el PDF deja el original en español.
_EXTRA_CONCEPTOS = {
    "bolsa de dormir (alquiler aparte)": ("sleeping bag (rented separately)", "saco de dormir (aluguel à parte)"),
    "bolsa de dormir": ("sleeping bag", "saco de dormir"),
    "seguro de viaje": ("travel insurance", "seguro de viagem"),
    "propinas": ("tips", "gorjetas"),
    "huayna picchu": ("Huayna Picchu", "Huayna Picchu"),
    "campamentos básicos": ("basic campsites", "acampamentos básicos"),
    "carpa doble y colchoneta": ("double tent and sleeping pad", "barraca dupla e isolante"),
    "domos o carpas premium": ("domes or premium tents", "domos ou barracas premium"),
    "hostal sencillo": ("simple hostel", "hostel simples"),
    "hotel 3 estrellas": ("3-star hotel", "hotel 3 estrelas"),
    "hotel turista en habitación doble": ("tourist hotel, double room", "hotel turista em quarto duplo"),
    "tren vistadome de regreso": ("Vistadome return train", "trem Vistadome de volta"),
}


def _traducir(concepto: str, lang: str) -> str:
    """Concepto del tarifario en el idioma del viajero; sin traducción, el original."""
    clave = concepto.strip().lower()
    if lang != "es":
        if clave in INCLUYE:
            return INCLUYE[clave][_POSICION[lang]]
        if clave in _EXTRA_CONCEPTOS:
            return _EXTRA_CONCEPTOS[clave][0 if lang == "en" else 1]
    return concepto.strip()


def _nombre_trek(o: OpcionCotizada, idioma: str) -> str:
    return nombre_trek(o.trek_id.rsplit("_", 1)[0], idioma if idioma in ("es", "en", "pt", "fr", "de") else "en")


def _paquete(resultado, opciones: list[OpcionCotizada], paquete: Paquete | None) -> Paquete:
    """El paquete de la pantalla. Sin él, solo el trek de la primera opción (sin extras ni recargo)."""
    paquete = paquete or _campo(resultado, "paquete", "", obligatorio=False)
    if paquete is not None:
        return paquete
    o = opciones[0]
    return Paquete(opcion=o, personas=o.personas, extras=[], modulo=[], opcionales=[], noches_cusco=0, estrellas=3,
                   metodo_pago="transferencia", porcentaje_recargo=0.0)


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


# ------------------------------------------------------------------ Ruta (segunda página)
TEXTOS_RUTA = {
    "es": {"titulo": "Ruta", "trazado": "Trazado (sin mapa de fondo; las líneas rectas no son el sendero real)",
           "perfil": "Perfil de altitud (km acumulados en línea recta)", "etapas": "Etapas y puntos",
           "cols": ["Día", "Punto", "Tipo", "Altitud"], "sin_alt": "sin dato de altitud", "parcial": "ruta parcial",
           "parcial_txt": "Ruta parcial: faltan los campamentos y el tramo alto de los días 1 y 2.",
           "ref": "Referencial: confirmar el recorrido con la agencia",
           "fuente": "Puntos clave de un itinerario de referencia de {dias} días; las rutas varían entre agencias.",
           "falta": "los puntos con línea punteada no tienen altitud en las fuentes",
           "tipos": {"inicio": "Inicio", "fin": "Fin", "campamento": "Campamento", "paso": "Paso", "sitio": "Lugar"}},
    "en": {"titulo": "Route", "trazado": "Layout (no background map; straight lines are not the real trail)",
           "perfil": "Altitude profile (cumulative straight-line km)", "etapas": "Stages and points",
           "cols": ["Day", "Point", "Type", "Altitude"], "sin_alt": "no altitude data", "parcial": "partial route",
           "parcial_txt": "Partial route: the campsites and the high section of days 1 and 2 are missing.",
           "ref": "For reference only: confirm the route with the agency",
           "fuente": "Key points of a reference itinerary of {dias} days; routes vary between agencies.",
           "falta": "points with a dotted line have no altitude in the sources",
           "tipos": {"inicio": "Start", "fin": "End", "campamento": "Campsite", "paso": "Pass", "sitio": "Place"}},
    "pt": {"titulo": "Rota", "trazado": "Traçado (sem mapa de fundo; as linhas retas não são a trilha real)",
           "perfil": "Perfil de altitude (km acumulados em linha reta)", "etapas": "Etapas e pontos",
           "cols": ["Dia", "Ponto", "Tipo", "Altitude"], "sin_alt": "sem dado de altitude", "parcial": "rota parcial",
           "parcial_txt": "Rota parcial: faltam os acampamentos e o trecho alto dos dias 1 e 2.",
           "ref": "Referencial: confirmar o percurso com a agência",
           "fuente": "Pontos-chave de um itinerário de referência de {dias} dias; as rotas variam entre agências.",
           "falta": "os pontos com linha pontilhada não têm altitude nas fontes",
           "tipos": {"inicio": "Início", "fin": "Fim", "campamento": "Acampamento", "paso": "Passo", "sitio": "Lugar"}},
}
COLOR_TIPO = {"inicio": LAGUNA, "fin": CUMBRE, "campamento": TIERRA, "paso": AMANECER, "sitio": SECUNDARIO}
RUTAS_PARCIALES = {"lares"}  # data/rutas/README.md: lares_4d.csv está incompleto


def _ruta_del_trek(o: OpcionCotizada) -> mapa.Ruta | None:
    """Ruta con datos del trek cotizado, o None (Choquequirao, Inca Jungle, Camino Inca corto) o si falla la lectura."""
    try:
        return mapa.cargar_ruta(o.trek_id.rsplit("_", 1)[0])
    except Exception:  # noqa: BLE001 - la ruta es un extra: nunca debe impedir la cotización
        return None


def _dibujo_trazado(ruta: mapa.Ruta, ancho: float, alto: float) -> Drawing:
    """Polilínea y puntos con nombre a partir de lat/lon; solo puntos de los CSV, sin mapa de fondo."""
    import math
    pts = ruta.puntos
    k = math.cos(math.radians(sum(p.latitud for p in pts) / len(pts)))  # corrige el ancho de un grado de longitud
    xs, ys = [p.longitud * k for p in pts], [p.latitud for p in pts]
    margen_x, margen_y = 70.0, 16.0
    dx, dy = (max(xs) - min(xs)) or 1e-6, (max(ys) - min(ys)) or 1e-6
    esc = min((ancho - 2 * margen_x) / dx, (alto - 2 * margen_y) / dy)
    ox = (ancho - dx * esc) / 2
    oy = (alto - dy * esc) / 2
    pos = [(ox + (x - min(xs)) * esc, oy + (y - min(ys)) * esc) for x, y in zip(xs, ys)]
    d = Drawing(ancho, alto)
    d.add(PolyLine([c for xy in pos for c in xy], strokeColor=LAGUNA, strokeWidth=1.6))
    for i, (p, (x, y)) in enumerate(zip(pts, pos)):
        d.add(Circle(x, y, 3.4, fillColor=COLOR_TIPO.get(p.tipo, SECUNDARIO), strokeColor=colors.white, strokeWidth=0.6))
        # Etiqueta a la derecha o a la izquierda según el espacio; se alterna arriba/abajo para no encimarse
        dy_txt = 5 if i % 2 == 0 else -9
        derecha = x < ancho - 95
        d.add(String(x + (5 if derecha else -5), y + dy_txt, p.lugar, fontName="Helvetica", fontSize=6.5,
                     fillColor=TINTA, textAnchor="start" if derecha else "end"))
    return d


def _dibujo_perfil(ruta: mapa.Ruta, ancho: float, alto: float) -> Drawing | None:
    """Perfil con los puntos que tienen altitud; los que no la tienen se marcan con una línea punteada."""
    pts = ruta.puntos
    km, acum = [0.0], 0.0
    for a, b in zip(pts, pts[1:]):
        acum += mapa.km_entre(a, b)
        km.append(acum)
    con = [(k, p) for k, p in zip(km, pts) if p.altitud_m is not None]
    if len(con) < 2 or not km[-1]:
        return None
    alts = [p.altitud_m for _, p in con]
    lo, hi = min(alts) - 150, max(alts) + 250
    izq, der, abajo, arriba = 34.0, 10.0, 22.0, 12.0
    sx = (ancho - izq - der) / km[-1]
    sy = (alto - abajo - arriba) / (hi - lo)
    X = lambda v: izq + v * sx  # noqa: E731
    Y = lambda a: abajo + (a - lo) * sy  # noqa: E731
    d = Drawing(ancho, alto)
    d.add(Line(izq, abajo, ancho - der, abajo, strokeColor=BORDE, strokeWidth=0.6))
    d.add(Line(izq, abajo, izq, alto - arriba, strokeColor=BORDE, strokeWidth=0.6))
    paso = 500 if hi - lo > 1500 else 250
    for a in range((int(lo) // paso + 1) * paso, int(hi), paso):
        d.add(Line(izq, Y(a), ancho - der, Y(a), strokeColor=colors.HexColor("#EEEAE0"), strokeWidth=0.3))
        d.add(String(izq - 3, Y(a) - 2, str(a), fontName="Helvetica", fontSize=6, fillColor=SECUNDARIO, textAnchor="end"))
    for k, p in zip(km, pts):  # puntos sin altitud: marca punteada desde el eje
        if p.altitud_m is None:
            d.add(Line(X(k), abajo, X(k), alto - arriba, strokeColor=AMANECER, strokeWidth=0.7, strokeDashArray=[2, 2]))
            d.add(String(X(k), abajo - 9, "?", fontName="Helvetica-Bold", fontSize=7, fillColor=TIERRA, textAnchor="middle"))
    d.add(PolyLine([c for k, p in con for c in (X(k), Y(p.altitud_m))], strokeColor=LAGUNA, strokeWidth=1.4))
    for i, (k, p) in enumerate(con):
        d.add(Circle(X(k), Y(p.altitud_m), 2.8, fillColor=TIERRA, strokeColor=colors.white, strokeWidth=0.5))
        d.add(String(X(k), Y(p.altitud_m) + (5 if i % 2 == 0 else 11), f"{p.lugar} {p.altitud_m}", fontName="Helvetica",
                     fontSize=5.8, fillColor=TINTA, textAnchor="middle"))
    return d


def _pagina_ruta(ruta: mapa.Ruta, lang: str, base: ParagraphStyle, peq: ParagraphStyle, h2: ParagraphStyle,
                 th: ParagraphStyle, nombre: str) -> list:
    """Flowables de la segunda página: trazado, perfil, lista de etapas y pie con atribución."""
    r = TEXTOS_RUTA[lang]
    parcial = ruta.ruta in RUTAS_PARCIALES
    titulo = f"{r['titulo']}: {nombre}" + (f" ({r['parcial']})" if parcial else "")
    dias = mapa.archivo_dias(ruta.archivo)
    out = [_p(titulo, h2), _p(r["fuente"].format(dias=dias), peq)]
    if parcial:
        out.append(_p(r["parcial_txt"], ParagraphStyle("parc", parent=peq, textColor=AVISO_TEXTO)))
    out += [_p(r["trazado"], peq), _dibujo_trazado(ruta, 180 * mm, 85 * mm)]
    perfil = _dibujo_perfil(ruta, 180 * mm, 55 * mm)
    if perfil is not None:
        extra = f" — {r['falta']}" if any(p.altitud_m is None for p in ruta.puntos) else ""
        out += [Spacer(1, 4), _p(r["perfil"] + extra, peq), perfil]
    filas = [[_p(c, th) for c in r["cols"]]]
    for p in ruta.puntos:
        alt = f"{p.altitud_m} m" if p.altitud_m is not None else r["sin_alt"]
        filas.append([_p(str(p.dia), base), _p(p.lugar, base), _p(r["tipos"].get(p.tipo, p.tipo), base), _p(alt, base)])
    tab = Table(filas, colWidths=[14 * mm, 76 * mm, 40 * mm, 50 * mm], repeatRows=1)
    tab.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), LAGUNA),
                             ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F5F1E8")]),
                             ("BOX", (0, 0), (-1, -1), 0.6, BORDE), ("INNERGRID", (0, 0), (-1, -1), 0.3, BORDE),
                             ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]))
    out += [_p(r["etapas"], h2), tab, Spacer(1, 6), _p(r["ref"], peq), _p(mapa.ATRIBUCION, peq)]
    return out


def generar_cotizacion_pdf(resultado, *, agencia: str = AGENCIA_POR_DEFECTO,
                           vigencia_dias: int = VIGENCIA_DIAS_POR_DEFECTO,
                           paquete: Paquete | None = None, contacto: str | None = None,
                           ahora: datetime | None = None) -> bytes:
    """Devuelve los bytes de un PDF A4 de una página (dos si el trek tiene ruta en data/rutas/). `ahora` fija el reloj en las pruebas.

    `paquete` es el que muestra la pantalla (core.paquete.armar_paquete con la selección del vendedor); si no se
    pasa, se usa `resultado.paquete` y, si tampoco existe, el trek de la primera opción sin extras.
    `contacto` es el contacto de la agencia para el pie; también se lee de perfil.contacto_agencia si existe."""
    perfil = _campo(resultado, "perfil", "")
    idioma = str(_campo(perfil, "idioma", "perfil.")).lower()[:2]
    opciones = _opciones(resultado)
    t = TEXTOS.get(idioma, TEXTOS["en"])
    nivel_txt = NIVEL_TXT.get(idioma, NIVEL_TXT["en"])
    lang = idioma if idioma in TEXTOS else "en"

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
    p = _paquete(resultado, opciones, paquete)
    o = p.opcion
    f = FRASES_PAQUETE[lang]

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
    fechas = _campo(perfil, "fecha_texto", "perfil.", obligatorio=False)
    if not fechas:
        mes = _campo(perfil, "mes_viaje", "perfil.", obligatorio=False)
        fechas = MESES.get(idioma, MESES["en"])[int(mes) - 1] if mes else t["sin_dato"]
    datos = [
        [_p(t["grupo"], peq), _p(f"{p.personas} {t['personas']}", base), _p(t["fechas"], peq), _p(fechas, base)],
        [_p("Trek", peq), _p(_nombre_trek(o, idioma), base), _p(t["idioma"], peq),
         _p(NOMBRE_IDIOMA.get(idioma, idioma), base)],
    ]
    tb = Table(datos, colWidths=[22 * mm, 68 * mm, 22 * mm, 68 * mm])
    tb.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.6, BORDE), ("INNERGRID", (0, 0), (-1, -1), 0.3, BORDE),
                            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                            ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
    hist += [_p(t["tus_datos"], h2), tb]

    # Paquete: una fila por línea (trek y cada extra); todos los montos son los de core.paquete.Paquete
    negrita = ParagraphStyle("negrita", parent=base, fontName="Helvetica-Bold")
    negrita_r = ParagraphStyle("negrita_r", parent=negrita, alignment=2, textColor=TIERRA)
    nivel = nivel_txt.get(o.nivel, o.nivel)
    trek_txt = f"{_nombre_trek(o, idioma)}, {o.dias} {f['dias']}, {nivel}" + (f" ({t['alt']})" if o.es_alternativa else "")
    filas = [[_p(f["cols"][0], th), _p(f["cols"][1], th), _p(f["cols"][2], thr)]]
    filas.append([_p(trek_txt, base), _p(f"{p.personas} × US$ {monto(o.precio_pp * 100, lang)}", base),
                  _p(f"US$ {monto(p.base_c, lang)}", tdr)])
    for c in p.componentes:
        nombre, _ = _nombre_y_beneficio(c, lang, {})
        if c.id in HOTEL.values():
            nombre = f"{c.noches} {f['noche_s'] if c.noches != 1 else f['noche']} {nombre}"
            detalle = f"{p.personas} × {c.noches} × US$ {monto(c.precio_c, lang)}"
        elif c.unidad == "por grupo":
            detalle = f"1 × US$ {monto(c.precio_c, lang)} ({f['grupo']})"
        elif c.unidad == "por noche":
            detalle = f"{p.personas} × {c.noches} × US$ {monto(c.precio_c, lang)}"
        else:
            detalle = f"{p.personas} × US$ {monto(c.precio_c, lang)}"
        filas.append([_p(nombre, base), _p(detalle, base), _p(f"US$ {monto(c.total_c, lang)}", tdr)])
    if p.recargo_c:
        metodo = METODOS.get(p.metodo_pago, p.metodo_pago)
        filas.append([_p(f"{f['recargo']} ({metodo}, {p.porcentaje_recargo:g} %)", base), _p("", base),
                      _p(f"US$ {monto(p.recargo_c, lang)}", tdr)])
    n_detalle = len(filas)
    filas += [[_p(f["total"], negrita), _p("", base), _p(f"US$ {monto(p.total_c, lang)}", negrita_r)],
              [_p(f["por_persona"], base), _p("", base), _p(f"US$ {monto(p.por_persona_c, lang)}", tdr)],
              [_p(f["deposito"], base), _p("", base), _p(f"US$ {monto(p.deposito_c, lang)}", tdr)],
              [_p(f["saldo"], base), _p("", base), _p(f"US$ {monto(p.saldo_c, lang)}", tdr)]]
    tab = Table(filas, colWidths=[85 * mm, 55 * mm, 40 * mm], repeatRows=1)
    tab.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), LAGUNA),
                             ("ROWBACKGROUNDS", (0, 1), (-1, n_detalle - 1), [colors.white, colors.HexColor("#F5F1E8")]),
                             ("LINEABOVE", (0, n_detalle), (-1, n_detalle), 1.2, CUMBRE),
                             ("BOX", (0, 0), (-1, -1), 0.6, BORDE), ("INNERGRID", (0, 0), (-1, -1), 0.3, BORDE),
                             ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                             ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
    hist += [_p(t["opciones"], h2), tab, Spacer(1, 3), _p(f"{t['moneda']} {t['nota_saldo']}", peq)]
    for otra in opciones:
        if (otra.trek_id, otra.nivel) != (o.trek_id, o.nivel):
            hist += [_p(f"{f['otra']}: {_nombre_trek(otra, idioma)}, {otra.dias} {f['dias']}: US$ {otra.precio_pp} "
                        f"{f['pp']} ({f['solo_trek']}).", peq)]
    if o.requiere_permiso:
        hist += [_p(t["permiso"], peq)]

    # Qué incluye y qué no (del tarifario), en el idioma del viajero
    hi = ParagraphStyle("hi", parent=base, fontName="Helvetica-Bold", textColor=LAGUNA)
    hn = ParagraphStyle("hn", parent=base, fontName="Helvetica-Bold", textColor=TIERRA)
    incl = Table([[_p(t["incluye"], hi), _p(t["no_incluye"], hn)],
                  [_p("; ".join(_traducir(x, lang) for x in o.incluye), base),
                   _p("; ".join(_traducir(x, lang) for x in o.no_incluye), base)]],
                 colWidths=[90 * mm, 90 * mm])
    incl.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
    hist += [Spacer(1, 6), incl]

    # Vigencia (supuesto)
    hist += [Spacer(1, 6),
             _p(f"{t['vigencia']}: {vigencia_dias} {f['dias_vig']} ({t['hasta']} {_fecha_texto(vence, idioma)}) "
                f"— {t['supuesto']}.", peq)]

    # Aviso de demostración, visible
    aviso = ParagraphStyle("aviso", parent=base, fontName="Helvetica-Bold", textColor=AVISO_TEXTO)
    av = Table([[_p(AVISO_DEMO, aviso)]], colWidths=[180 * mm])
    av.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), AVISO_FONDO), ("BOX", (0, 0), (-1, -1), 0.8, AMANECER),
                            ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                            ("LEFTPADDING", (0, 0), (-1, -1), 8)]))
    hist += [Spacer(1, 10), av, Spacer(1, 8)]
    pie = f"{f['preparado']} {AGENCIA_POR_DEFECTO}"
    contacto = contacto or _campo(perfil, "contacto_agencia", "perfil.", obligatorio=False)
    if contacto:
        pie += f" · {contacto}"
    hist += [_p(pie, ParagraphStyle("pie", parent=peq, alignment=1))]

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm, topMargin=15 * mm,
                            bottomMargin=15 * mm, title=f"{agencia}: cotización", author=agencia,
                            pageCompression=0)
    marco = A4[0] - 30 * mm, A4[1] - 30 * mm
    # KeepInFrame reduce si algo no cabe: la cotización siempre queda en una sola página
    contenido = [KeepInFrame(marco[0], marco[1], hist, mode="shrink")]
    ruta = _ruta_del_trek(o)
    if ruta is not None:  # segunda página solo si el trek tiene datos de ruta
        try:
            pagina = _pagina_ruta(ruta, lang, base, peq, h2, th, _nombre_trek(o, idioma))
            contenido += [PageBreak(), KeepInFrame(marco[0], marco[1], pagina, mode="shrink")]
        except Exception:  # noqa: BLE001 - sin ruta el PDF sigue siendo de una página
            pass
    doc.build(contenido)
    return buf.getvalue()
