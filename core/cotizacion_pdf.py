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
import re
import unicodedata
from contextvars import ContextVar
from datetime import date, datetime, timezone
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.graphics.shapes import Circle, Drawing, Line, PolyLine, Rect, String
from reportlab.platypus import (KeepInFrame, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

from core.cotizacion import NOMBRE_NIVEL, OpcionCotizada
from core.mapa import ATRIBUCION, Ruta, cargar_ruta, km_entre
from core.paquete import Paquete, _nombre_y_beneficio, monto

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

AVISO_DEMO = "Datos de demostración. Confirmar disponibilidad y permisos antes de reservar."  # es (por defecto)

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
        "dias": "días", "dia": "día", "paquete": "Tu paquete", "concepto": "Concepto", "calculo": "Cálculo",
        "monto": "Monto", "total_grupo": "Total del grupo", "por_persona": "Por persona", "recargo": "Recargo por pago con",
        "del_total": "del total", "total_pagar": "Total a pagar", "deposito": "Depósito (50 %)", "saldo": "Saldo",
        "noche": "noche", "noches": "noches", "por_grupo": "por grupo", "otras": "Otras opciones",
        "pie": "Preparado con Abra Travel", "contacto": "Contacto",
        "tarjeta": "tarjeta", "paypal": "PayPal",
        "ruta": "Ruta", "ruta_parcial": "ruta parcial", "referencial": "Referencial: confirmar el recorrido con la agencia.",
        "mapa_nota": "Los puntos están unidos con líneas rectas: no es el sendero exacto.",
        "perfil": "Perfil de altitud", "perfil_nota": "Km acumulados en línea recta entre puntos. × = punto sin altitud en las fuentes.",
        "puntos": "Puntos de la ruta", "altitud": "Altitud", "sin_altitud": "sin dato", "dia_n": "Día",
        "sin_perfil": "Sin altitudes suficientes para dibujar el perfil.",
        "parcial_nota": "Ruta parcial: faltan puntos del recorrido (campamentos y tramo alto).",
        "aviso_demo": "Datos de demostración. Confirmar disponibilidad y permisos antes de reservar.",
        "itinerario_ref": "itinerario de referencia de {n} días (datos del repositorio)",
        "ref_difiere": "Tu cotización es de {dias} días: la agencia confirmará cómo se organiza la opción cotizada.",
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
        "dias": "days", "dia": "day", "paquete": "Your package", "concepto": "Item", "calculo": "Calculation",
        "monto": "Amount", "total_grupo": "Group total", "por_persona": "Per person", "recargo": "Surcharge for paying by",
        "del_total": "of the total", "total_pagar": "Total to pay", "deposito": "Deposit (50 %)", "saldo": "Balance",
        "noche": "night", "noches": "nights", "por_grupo": "per group", "otras": "Other options",
        "pie": "Prepared with Abra Travel", "contacto": "Contact",
        "tarjeta": "card", "paypal": "PayPal",
        "ruta": "Route", "ruta_parcial": "partial route", "referencial": "For reference: confirm the route with the agency.",
        "mapa_nota": "Points are joined by straight lines: this is not the exact trail.",
        "perfil": "Altitude profile", "perfil_nota": "Cumulative km in a straight line between points. × = point with no altitude in the sources.",
        "puntos": "Route points", "altitud": "Altitude", "sin_altitud": "no data", "dia_n": "Day",
        "sin_perfil": "Not enough altitude data to draw the profile.",
        "parcial_nota": "Partial route: some points of the route are missing (camps and the high section).",
        "aviso_demo": "Demo data. Confirm availability and permits before booking.",
        "itinerario_ref": "reference itinerary of {n} days (repository data)",
        "ref_difiere": "Your quote is for {dias} days: the agency will confirm how the quoted option is organised.",
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
        "dias": "dias", "dia": "dia", "paquete": "Seu pacote", "concepto": "Item", "calculo": "Cálculo",
        "monto": "Valor", "total_grupo": "Total do grupo", "por_persona": "Por pessoa", "recargo": "Acréscimo por pagamento com",
        "del_total": "do total", "total_pagar": "Total a pagar", "deposito": "Entrada (50 %)", "saldo": "Saldo",
        "noche": "noite", "noches": "noites", "por_grupo": "por grupo", "otras": "Outras opções",
        "pie": "Preparado com Abra Travel", "contacto": "Contato",
        "tarjeta": "cartão", "paypal": "PayPal",
        "ruta": "Rota", "ruta_parcial": "rota parcial", "referencial": "Referencial: confirmar o percurso com a agência.",
        "mapa_nota": "Os pontos estão unidos por linhas retas: não é a trilha exata.",
        "perfil": "Perfil de altitude", "perfil_nota": "Km acumulados em linha reta entre pontos. × = ponto sem altitude nas fontes.",
        "puntos": "Pontos da rota", "altitud": "Altitude", "sin_altitud": "sem dado", "dia_n": "Dia",
        "sin_perfil": "Altitudes insuficientes para desenhar o perfil.",
        "parcial_nota": "Rota parcial: faltam pontos do percurso (acampamentos e trecho alto).",
        "aviso_demo": "Dados de demonstração. Confirmar disponibilidade e permissões antes de reservar.",
        "itinerario_ref": "itinerário de referência de {n} dias (dados do repositório)",
        "ref_difiere": "Sua cotação é de {dias} dias: a agência confirmará como a opção cotada é organizada.",
    },
}
# Conceptos de "incluye / no incluye" del tarifario (data/tarifario_demo.csv). Clave en minúsculas; si un concepto
# no está aquí se deja el original (en español).
CONCEPTOS = {
    "guía bilingüe": {"en": "bilingual guide", "pt": "guia bilíngue"},
    "transporte de ida": {"en": "one-way transport", "pt": "transporte de ida"},
    "transporte ida y vuelta desde cusco": {"en": "round-trip transport from Cusco", "pt": "transporte de ida e volta desde Cusco"},
    "comidas durante el trek": {"en": "meals during the trek", "pt": "refeições durante a trilha"},
    "entrada a machu picchu": {"en": "Machu Picchu entrance", "pt": "entrada em Machu Picchu"},
    "tren de regreso a ollantaytambo": {"en": "return train to Ollantaytambo", "pt": "trem de volta a Ollantaytambo"},
    "campamentos básicos": {"en": "basic camps", "pt": "acampamentos básicos"},
    "carpa doble y colchoneta": {"en": "double tent and sleeping mat", "pt": "barraca dupla e isolante"},
    "domos o carpas premium": {"en": "domes or premium tents", "pt": "domos ou barracas premium"},
    "bolsa de dormir": {"en": "sleeping bag", "pt": "saco de dormir"},
    "tren vistadome de regreso": {"en": "Vistadome return train", "pt": "trem Vistadome de volta"},
    "permiso del camino inca": {"en": "Inca Trail permit", "pt": "permissão da Trilha Inca"},
    "porteadores": {"en": "porters", "pt": "carregadores"},
    "entrada al sitio arqueológico de choquequirao": {"en": "Choquequirao archaeological site entrance",
                                                       "pt": "entrada no sítio arqueológico de Choquequirao"},
    "bolsa de dormir (alquiler aparte)": {"en": "sleeping bag (rental extra)", "pt": "saco de dormir (aluguel à parte)"},
    "seguro de viaje": {"en": "travel insurance", "pt": "seguro de viagem"},
    "propinas": {"en": "tips", "pt": "gorjetas"},
    "huayna picchu": {"en": "Huayna Picchu", "pt": "Huayna Picchu"},
    "1 noche en aguas calientes": {"en": "1 night in Aguas Calientes", "pt": "1 noite em Aguas Calientes"},
    "almuerzo del día de caminata": {"en": "lunch on the hiking day", "pt": "almoço no dia da caminhada"},
    "bicicleta y casco para la bajada": {"en": "bike and helmet for the descent", "pt": "bicicleta e capacete para a descida"},
    "hostal sencillo": {"en": "simple hostel", "pt": "hostel simples"},
    "hotel 3 estrellas": {"en": "3-star hotel", "pt": "hotel 3 estrelas"},
    "hotel turista en habitación doble": {"en": "tourist hotel, double room", "pt": "hotel turista em quarto duplo"},
    "tren al km 104": {"en": "train to KM 104", "pt": "trem até o KM 104"},
}


def traducir_concepto(texto: str, idioma: str) -> str:
    """El concepto en el idioma del viajero; si no hay traducción, el original."""
    t = CONCEPTOS.get(texto.strip().lower(), {}).get(idioma)
    if not t:
        return texto
    return t[:1].upper() + t[1:] if texto[:1].isupper() else t


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


_IDIOMA_PDF: ContextVar[str] = ContextVar("idioma_pdf", default="en")
_ESTRELLAS = {"es": r"de \1 estrellas", "en": r"\1-star", "pt": r"\1 estrelas"}


def _limpio(texto: str, idioma: str | None = None) -> str:
    """Helvetica (WinAnsi) no trae ★ ni otros símbolos: se reemplazan por texto y, si algo no cabe en WinAnsi,
    se quita el acento o el carácter. Así el PDF nunca muestra cuadrados. No toca el texto de la respuesta."""
    idioma = idioma or _IDIOMA_PDF.get()
    texto = str(texto)
    if idioma == "es":  # "hotel 3★" -> "hotel de 3 estrellas"
        texto = re.sub(r"hotel (\d)\s*★", r"hotel de \1 estrellas", texto)
    texto = re.sub(r"(\d)\s*★", _ESTRELLAS.get(idioma, _ESTRELLAS["en"]), texto)
    texto = texto.replace("★", "").replace("→", "-").replace("≈", "~").replace("–", "-")
    salida = []
    for c in texto:
        try:
            c.encode("cp1252")
            salida.append(c)
        except UnicodeEncodeError:
            base = unicodedata.normalize("NFKD", c).encode("ascii", "ignore").decode()
            salida.append(base)
    return "".join(salida)


def _p(texto: str, estilo: ParagraphStyle) -> Paragraph:
    return Paragraph(escape(_limpio(texto)), estilo)


COLOR_TIPO = {"inicio": LAGUNA, "fin": CUMBRE, "campamento": TIERRA, "paso": colors.HexColor("#B4471F"),
              "sitio": SECUNDARIO}


def _choca(caja, cajas, segmentos, puntos) -> bool:
    """¿La caja (x0, y0, x1, y1) pisa otra etiqueta, la línea de la ruta o un punto?"""
    x0, y0, x1, y1 = caja
    if any(not (x1 < a or x0 > c or y1 < b_ or y0 > d) for a, b_, c, d in cajas):
        return True
    for (ax, ay), (bx, by) in segmentos:
        for i in range(21):
            px, py = ax + (bx - ax) * i / 20, ay + (by - ay) * i / 20
            if x0 - 1 <= px <= x1 + 1 and y0 - 1 <= py <= y1 + 1:
                return True
    return any(x0 - 3 <= px <= x1 + 3 and y0 - 3 <= py <= y1 + 3 for px, py in puntos)


def _colocar_etiquetas(xy, nombres, ancho, alto, tam=6.8):
    """Para cada punto elige lado (derecha o izquierda) y desplazamiento vertical sin pisar otras etiquetas, la
    línea de la ruta ni otros puntos. Devuelve (x_texto, y_texto, ancla, línea_guía) por punto."""
    segmentos = list(zip(xy, xy[1:]))
    cajas, salida = [], []
    for i, ((x, y), nombre) in enumerate(zip(xy, nombres)):
        w = len(nombre) * tam * 0.52 + 2
        # primero el lado con más espacio libre; luego el otro
        lados = ["der", "izq"] if x < ancho / 2 else ["izq", "der"]
        elegido = None
        for dy in (0, 8, -8, 16, -16, 24, -24, 32, -32):
            for lado in lados:
                x0 = x + 6 if lado == "der" else x - 6 - w
                y0 = y - 2.5 + dy
                caja = (x0, y0 - 1, x0 + w, y0 + tam + 1)
                if x0 < 2 or x0 + w > ancho - 2 or y0 < 2 or y0 + tam > alto - 2:
                    continue
                if not _choca(caja, cajas, [sg for k, sg in enumerate(segmentos) if k not in (i - 1, i)] +
                              [sg for k, sg in enumerate(segmentos) if k in (i - 1, i)],
                              [pt for k, pt in enumerate(xy) if k != i]):
                    elegido = (lado, dy, caja, x0, y0)
                    break
            if elegido:
                break
        if elegido is None:  # sin sitio libre: lado preferido sin desplazar (poco probable con <= 12 puntos)
            lado = lados[0]
            x0 = x + 6 if lado == "der" else x - 6 - w
            elegido = (lado, 0, (x0, y - 3.5, x0 + w, y + tam), x0, y - 2.5)
        lado, dy, caja, x0, y0 = elegido
        cajas.append(caja)
        salida.append((x0 if lado == "der" else x0 + w, y0, "start" if lado == "der" else "end", dy != 0))
    return salida


def _dibujo_mapa(ruta: Ruta, ancho: float, alto: float) -> Drawing:
    """Polilínea y puntos con nombre, sin mapa de fondo y sin red. Proyección plana (grados, corregida por latitud)."""
    import math

    pts = ruta.puntos
    lat0 = sum(p.latitud for p in pts) / len(pts)
    xs = [p.longitud * math.cos(math.radians(lat0)) for p in pts]
    ys = [p.latitud for p in pts]
    pad_x, pad_y = 95, 16
    caja_w, caja_h = ancho - 2 * pad_x, alto - 2 * pad_y
    sx = (max(xs) - min(xs)) or 1e-9
    sy = (max(ys) - min(ys)) or 1e-9
    escala = min(caja_w / sx, caja_h / sy)
    ox = pad_x + (caja_w - sx * escala) / 2
    oy = pad_y + (caja_h - sy * escala) / 2
    xy = [(ox + (x - min(xs)) * escala, oy + (y - min(ys)) * escala) for x, y in zip(xs, ys)]
    d = Drawing(ancho, alto)
    d.add(Rect(0, 0, ancho, alto, fillColor=colors.white, strokeColor=BORDE, strokeWidth=0.6))
    d.add(PolyLine([c for par in xy for c in par], strokeColor=LAGUNA, strokeWidth=1.6, strokeDashArray=[4, 2]))
    nombres = [_limpio(f"{i + 1}. {p.lugar}") for i, p in enumerate(pts)]
    for (tx, ty, ancla, guia), (x, y) in zip(_colocar_etiquetas(xy, nombres, ancho, alto), xy):
        if guia:  # etiqueta desplazada: una línea fina la une a su punto
            d.add(Line(x, y, tx + (-1 if ancla == "start" else 1), ty + 2.5, strokeColor=BORDE, strokeWidth=0.5))
    for p, (x, y), nombre, (tx, ty, ancla, _) in zip(pts, xy, nombres, _colocar_etiquetas(xy, nombres, ancho, alto)):
        d.add(Circle(x, y, 3.4, fillColor=COLOR_TIPO.get(p.tipo, SECUNDARIO), strokeColor=colors.white, strokeWidth=0.8))
        d.add(String(tx, ty, nombre, fontName="Helvetica", fontSize=6.8, fillColor=TINTA, textAnchor=ancla))
    return d


def _paso_km(kmax: float) -> int:
    for paso in (1, 2, 5, 10, 20, 25, 50, 100):
        if kmax / paso <= 8:
            return paso
    return 100


def _dibujo_perfil(ruta: Ruta, ancho: float, alto: float, t: dict) -> Drawing:
    """Altitud contra km acumulados en línea recta, con marcas de km. Los puntos sin altitud van con × abajo."""
    acum, previo, datos = 0.0, None, []
    for i, p in enumerate(ruta.puntos):
        if previo is not None:
            acum += km_entre(previo, p)
        previo = p
        datos.append((i + 1, acum, p.altitud_m))
    con = [(n, km, a) for n, km, a in datos if a is not None]
    d = Drawing(ancho, alto)
    d.add(Rect(0, 0, ancho, alto, fillColor=colors.white, strokeColor=BORDE, strokeWidth=0.6))
    if len(con) < 2:
        d.add(String(10, alto / 2, t["sin_perfil"], fontName="Helvetica", fontSize=8, fillColor=SECUNDARIO))
        return d
    izq, der, aba, arr = 44, 18, 40, 12
    lo = (min(a for _, _, a in con) // 500) * 500
    hi = -(-max(a for _, _, a in con) // 500) * 500
    hi = hi if hi > lo else lo + 500
    kmax = datos[-1][1] or 1.0
    fx = lambda km: izq + (ancho - izq - der) * km / kmax  # noqa: E731
    fy = lambda a: aba + (alto - aba - arr) * (a - lo) / (hi - lo)  # noqa: E731
    paso = 500 if hi - lo <= 2500 else 1000
    for v in range(int(lo), int(hi) + 1, paso):
        d.add(Line(izq, fy(v), ancho - der, fy(v), strokeColor=BORDE, strokeWidth=0.4))
        d.add(String(izq - 4, fy(v) - 2.5, f"{v} m", fontName="Helvetica", fontSize=6.5, fillColor=SECUNDARIO,
                     textAnchor="end"))
    # eje horizontal con marcas de km
    d.add(Line(izq, aba, ancho - der, aba, strokeColor=SECUNDARIO, strokeWidth=0.6))
    pk = _paso_km(kmax)
    km = 0
    while km <= kmax + 1e-9:
        d.add(Line(fx(km), aba, fx(km), aba - 3, strokeColor=SECUNDARIO, strokeWidth=0.6))
        d.add(String(fx(km), aba - 11, str(km), fontName="Helvetica", fontSize=6.5, fillColor=SECUNDARIO,
                     textAnchor="middle"))
        km += pk
    d.add(String(ancho - der + 2, aba - 11, "km", fontName="Helvetica-Bold", fontSize=6.5, fillColor=SECUNDARIO))
    d.add(PolyLine([c for _, km_, a in con for c in (fx(km_), fy(a))], strokeColor=LAGUNA, strokeWidth=1.6))
    for n, km_, a in con:
        d.add(Circle(fx(km_), fy(a), 2.6, fillColor=LAGUNA, strokeColor=colors.white, strokeWidth=0.6))
        d.add(String(fx(km_), fy(a) + 5, str(n), fontName="Helvetica-Bold", fontSize=6.5, fillColor=TINTA,
                     textAnchor="middle"))
    for n, km_, a in datos:
        if a is None:
            x = fx(km_)
            d.add(Line(x - 2.5, aba - 22 - 2.5, x + 2.5, aba - 22 + 2.5, strokeColor=TIERRA, strokeWidth=1))
            d.add(Line(x - 2.5, aba - 22 + 2.5, x + 2.5, aba - 22 - 2.5, strokeColor=TIERRA, strokeWidth=1))
            d.add(String(x, aba - 32, str(n), fontName="Helvetica", fontSize=6, fillColor=TIERRA, textAnchor="middle"))
    return d


def _pagina_ruta(ruta: Ruta, trek: str, dias_cotizados: int, t: dict, base, peq, h2) -> list:
    """Segunda página: trazado, perfil de altitud y lista de puntos. Solo datos de data/rutas/.

    Es un itinerario de REFERENCIA con los días de los datos (p. ej. 5 días del Salkantay): si la opción cotizada
    tiene otros días, se dice que la agencia confirmará cómo se organiza; no se inventa un itinerario."""
    parcial = ruta.ruta == "lares"
    dias_ref = ruta.dias_itinerario
    titulo = f"{t['ruta']}: {trek}"
    if dias_ref:
        titulo += f" - {t['itinerario_ref'].format(n=dias_ref)}"
    if parcial:
        titulo += f" ({t['ruta_parcial']})"
    h = [_p(titulo, h2), Spacer(1, 2)]
    if dias_ref and dias_ref != dias_cotizados:
        h += [_p(t["ref_difiere"].format(dias=dias_cotizados), peq), Spacer(1, 2)]
    h += [_dibujo_mapa(ruta, 180 * mm, 100 * mm), Spacer(1, 2), _p(t["mapa_nota"], peq)]
    if parcial:
        h += [_p(t["parcial_nota"], peq)]
    h += [_p(t["perfil"], h2), _dibujo_perfil(ruta, 180 * mm, 56 * mm, t), Spacer(1, 2), _p(t["perfil_nota"], peq),
          _p(t["puntos"], h2)]
    fila = lambda i, p: [_p(str(i + 1), peq), _p(p.lugar, base), _p(f"{t['dia_n']} {p.dia}", peq),  # noqa: E731
                         _p(f"{p.altitud_m:,} m".replace(",", " ") if p.altitud_m is not None else t["sin_altitud"], peq)]
    filas = [fila(i, p) for i, p in enumerate(ruta.puntos)]
    mitad = (len(filas) + 1) // 2
    izq, der = filas[:mitad], filas[mitad:]
    der += [["", "", "", ""]] * (len(izq) - len(der))
    cuerpo = [a + b for a, b in zip(izq, der)]
    tab = Table(cuerpo, colWidths=[6 * mm, 46 * mm, 14 * mm, 20 * mm] * 2)
    tab.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LINEBELOW", (0, 0), (-1, -1), 0.3, BORDE),
                             ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                             ("LEFTPADDING", (0, 0), (-1, -1), 2)]))
    h += [tab, Spacer(1, 6), _p(f"{t['referencial']} {ATRIBUCION}.", peq)]
    return h


def _tabla_opciones(opciones, t, nivel_txt, th, thr, base, peq, tdr, tdrb, h2):
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
    return [_p(t["opciones"], h2), tab, Spacer(1, 3), _p(f"{t['moneda']} {t['nota_saldo']}", peq)]


def _tabla_paquete(paquete: Paquete, idioma: str, t, th, thr, base, peq, tdr, tdrb, h2, opciones):
    """Una fila por línea del paquete y los totales, depósito y saldo de Paquete (sin recalcular)."""
    m = idioma if idioma in TEXTOS else "en"

    def usd(c: int) -> str:
        return f"US$ {monto(c, m)}"

    filas = [[_p(t["concepto"], th), _p(t["calculo"], th), _p(t["monto"], thr)]]
    for concepto, calculo, c in _linea_paquete(paquete, m, t):
        filas.append([_p(concepto, base), _p(calculo, peq), _p(usd(c), tdr)])
    negrita = []
    filas.append([_p(t["total_grupo"], base), _p("", peq), _p(usd(paquete.subtotal_c), tdrb)])
    negrita.append(len(filas) - 1)
    if paquete.recargo_c:
        metodo = t.get(paquete.metodo_pago, paquete.metodo_pago)
        filas.append([_p(f"{t['recargo']} {metodo}", base), _p(f"{paquete.porcentaje_recargo:g} % {t['del_total']}", peq),
                      _p(usd(paquete.recargo_c), tdr)])
        filas.append([_p(t["total_pagar"], base), _p("", peq), _p(usd(paquete.total_c), tdrb)])
        negrita.append(len(filas) - 1)
    filas.append([_p(t["por_persona"], base), _p("", peq), _p(usd(paquete.por_persona_c), tdr)])
    filas.append([_p(t["deposito"], base), _p("", peq), _p(usd(paquete.deposito_c), tdr)])
    filas.append([_p(t["saldo"], base), _p(t["nota_saldo"], peq), _p(usd(paquete.saldo_c), tdr)])
    tab = Table(filas, colWidths=[78 * mm, 66 * mm, 36 * mm], repeatRows=1)
    estilo = [("BACKGROUND", (0, 0), (-1, 0), LAGUNA), ("BOX", (0, 0), (-1, -1), 0.6, BORDE),
              ("INNERGRID", (0, 0), (-1, -1), 0.3, BORDE), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
              ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]
    estilo += [("BACKGROUND", (0, i), (-1, i), colors.HexColor("#F5F1E8")) for i in negrita]
    tab.setStyle(TableStyle(estilo))
    salida = [_p(t["paquete"], h2), tab, Spacer(1, 3), _p(t["moneda"], peq)]
    otras = [o for o in opciones if o is not paquete.opcion and (o.trek_id, o.nivel) != (paquete.opcion.trek_id, paquete.opcion.nivel)]
    if otras:
        texto = "; ".join(f"{o.trek}, {o.dias} {t['dias']}: US$ {monto(o.precio_pp * 100, m)} {t['por_persona'].lower()}"
                          for o in otras)
        salida += [_p(f"{t['otras']}: {texto}.", peq)]
    return salida


def _linea_paquete(paquete: Paquete, idioma: str, t: dict) -> list[tuple[str, str, int]]:
    """(concepto, cálculo, monto en centavos) de cada línea del paquete, con los números de Paquete: el mismo
    código que arma el mensaje y el panel "Ajustar el paquete". Aquí no se recalcula nada."""
    o, p = paquete.opcion, paquete
    nivel_txt = NIVEL_TXT.get(idioma, NIVEL_TXT["en"]).get(o.nivel, o.nivel)
    dias = t["dia"] if o.dias == 1 else t["dias"]
    grupo = f"{p.personas}"
    filas = [(f"{o.trek}, {o.dias} {dias}, {nivel_txt}" + (f" ({t['alt']})" if o.es_alternativa else ""),
              f"US$ {monto(o.precio_pp * 100, idioma)} × {grupo}", p.base_c)]
    for c in p.componentes:
        nombre, _ = _nombre_y_beneficio(c, idioma, {})
        precio = f"US$ {monto(c.precio_c, idioma)}"
        if c.unidad == "por grupo":
            calculo = f"{precio} ({t['por_grupo']})"
        elif c.unidad == "por noche":
            noches = t["noche"] if c.noches == 1 else t["noches"]
            calculo = f"{precio} × {c.noches} {noches} × {grupo}"
        else:
            calculo = f"{precio} × {grupo}"
        if c.id in ("hotel_cusco_3", "hotel_cusco_4"):
            nombre = f"{c.noches} {t['noche'] if c.noches == 1 else t['noches']} {nombre}"
        filas.append((nombre[:1].upper() + nombre[1:], calculo, c.total_c))
    return filas


def generar_cotizacion_pdf(resultado, *, agencia: str = AGENCIA_POR_DEFECTO,
                           vigencia_dias: int = VIGENCIA_DIAS_POR_DEFECTO,
                           ahora: datetime | None = None, paquete: Paquete | None = None,
                           contacto: str | None = None, _con_ruta: bool = True) -> bytes:
    """Devuelve los bytes de un PDF A4. `ahora` fija el reloj en las pruebas.

    `paquete`: el paquete ajustado (core.paquete.Paquete) que se ve en pantalla y en el mensaje. Si no se pasa,
    se usa el de `resultado.paquete`; si tampoco hay, la tabla muestra solo el precio del trek.
    """
    perfil = _campo(resultado, "perfil", "")
    idioma = str(_campo(perfil, "idioma", "perfil.")).lower()[:2]
    opciones = _opciones(resultado)
    paquete = paquete or _campo(resultado, "paquete", "", obligatorio=False)
    if not isinstance(paquete, Paquete):
        paquete = None
    idioma_monto = idioma if idioma in TEXTOS else "en"
    t = TEXTOS.get(idioma, TEXTOS["en"])
    nivel_txt = NIVEL_TXT.get(idioma, NIVEL_TXT["en"])
    _IDIOMA_PDF.set(idioma if idioma in TEXTOS else "en")

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

    if paquete is not None:
        hist += _tabla_paquete(paquete, idioma, t, th, thr, base, peq, tdr, tdrb, h2, opciones)
    else:
        hist += _tabla_opciones(opciones, t, nivel_txt, th, thr, base, peq, tdr, tdrb, h2)
    if any(o.requiere_permiso for o in opciones):
        hist += [_p(t["permiso"], peq)]

    # Qué incluye y qué no (del tarifario; las listas vienen en español)
    ref = opciones[0]
    incl = Table([[_p(t["incluye"], ParagraphStyle("hi", parent=base, fontName="Helvetica-Bold", textColor=LAGUNA)),
                   _p(t["no_incluye"], ParagraphStyle("hn", parent=base, fontName="Helvetica-Bold", textColor=TIERRA))],
                  [_p("; ".join(traducir_concepto(x, idioma) for x in ref.incluye), base),
                   _p("; ".join(traducir_concepto(x, idioma) for x in ref.no_incluye), base)]],
                 colWidths=[90 * mm, 90 * mm])
    incl.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
    hist += [Spacer(1, 6), incl]

    # Vigencia (supuesto)
    hist += [Spacer(1, 6),
             _p(f"{t['vigencia']}: {vigencia_dias} {t['dia'] if int(vigencia_dias) == 1 else t['dias']} ({t['hasta']} {_fecha_texto(vence, idioma)}) — {t['supuesto']}.", peq)]

    # Aviso de demostración, visible
    aviso = ParagraphStyle("aviso", parent=base, fontName="Helvetica-Bold", textColor=AVISO_TEXTO)
    av = Table([[_p(t["aviso_demo"], aviso)]], colWidths=[180 * mm])
    av.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), AVISO_FONDO), ("BOX", (0, 0), (-1, -1), 0.8, AMANECER),
                            ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                            ("LEFTPADDING", (0, 0), (-1, -1), 8)]))
    hist += [Spacer(1, 10), av]
    pie = f"{t['pie']}" + (f" · {t['contacto']}: {contacto}" if contacto else "")
    hist += [Spacer(1, 6), _p(pie, peq)]

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm, topMargin=15 * mm,
                            bottomMargin=15 * mm, title=f"{agencia}: cotización", author=agencia,
                            pageCompression=0)
    marco = A4[0] - 30 * mm, A4[1] - 30 * mm
    # KeepInFrame reduce si algo no cabe: la cotización siempre queda en una sola página
    paginas = [KeepInFrame(marco[0], marco[1], hist, mode="shrink")]
    try:  # segunda página solo si hay datos de ruta para el trek; si algo falla, el PDF sigue siendo de una página
        elegida = paquete.opcion if paquete is not None else opciones[0]
        ruta = cargar_ruta(elegida.trek_id.rsplit("_", 1)[0]) if _con_ruta else None
        if ruta is not None:
            h2r = ParagraphStyle("h2r", parent=base, fontName="Helvetica-Bold", fontSize=11, leading=14, textColor=LAGUNA,
                                 spaceBefore=6, spaceAfter=3)
            paginas += [PageBreak(), KeepInFrame(marco[0], marco[1], _pagina_ruta(ruta, elegida.trek, elegida.dias, t, base, peq, h2r),
                                                 mode="shrink")]
    except Exception:  # noqa: BLE001
        paginas = paginas[:1]
    try:
        doc.build(paginas)
    except Exception:  # noqa: BLE001 - si la página de ruta falla al dibujarse, se entrega la cotización sola
        if len(paginas) == 1 or not _con_ruta:
            raise
        return generar_cotizacion_pdf(resultado, agencia=agencia, vigencia_dias=vigencia_dias, ahora=ahora,
                                      paquete=paquete, contacto=contacto, _con_ruta=False)
    return buf.getvalue()
