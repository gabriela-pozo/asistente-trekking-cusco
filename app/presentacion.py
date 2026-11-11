"""Presentación: convierte los datos del resultado en texto legible y en HTML de la interfaz.

Solo da formato. No calcula precios ni cambia lo que decide el resto del código.
"""
from __future__ import annotations

from html import escape

from ai.fecha import MESES
from core.cotizacion import NOMBRE_NIVEL, NOMBRE_RUTA

IDIOMAS = {
    "es": "Español", "en": "Inglés", "pt": "Portugués", "fr": "Francés", "de": "Alemán", "it": "Italiano",
    "nl": "Neerlandés", "he": "Hebreo", "ja": "Japonés", "zh": "Chino", "ko": "Coreano", "ru": "Ruso",
}

# Advertencias que impiden enviar el mensaje tal cual (van en rojo y arriba).
_GRAVES = ("no están en la cotización", "no está en tu tarifario", "no coincide", "no dice el precio")


def idioma(codigo: str | None) -> str:
    return IDIOMAS.get((codigo or "").lower(), (codigo or "").upper())


def mes(numero: int | None) -> str:
    return MESES[numero - 1] if numero and 1 <= numero <= 12 else ""


def nivel(codigo: str | None) -> str:
    return NOMBRE_NIVEL.get(codigo or "", codigo or "").capitalize()


def usd(monto: float | int) -> str:
    """1200 -> 'US$ 1 200' (espacio fino que no se separa entre miles); 27.5 -> 'US$ 27,50'."""
    centavos = int(round(float(monto) * 100))
    entero = f"{centavos // 100:,}".replace(",", " ")
    return f"US$ {entero}" + (f",{centavos % 100:02d}" if centavos % 100 else "")


def separar_advertencias(advertencias: list[str]) -> tuple[list[str], list[str]]:
    """(graves, por revisar). Graves: montos inventados, depósito que no cuadra, trek sin precio, sin precio."""
    graves = [a for a in advertencias if any(g in a for g in _GRAVES)]
    return graves, [a for a in advertencias if a not in graves]


def lista_markdown(textos: list[str]) -> str:
    """Viñetas para st.error / st.warning. El signo $ se escapa: en markdown de Streamlit abre una fórmula."""
    return "\n".join(f"- {t.replace('$', chr(92) + '$')}" for t in textos)


def fichas_perfil(perfil) -> list[tuple[str, str]]:
    """(dato, valor legible) de lo que el viajero sí dijo, en orden de importancia para cotizar."""
    datos = [
        ("Trek", ", ".join(NOMBRE_RUTA.get(t, t) for t in perfil.treks_de_interes)),
        ("Personas", str(perfil.num_personas or "")),
        ("Mes del viaje", mes(perfil.mes_viaje)),
        ("Fechas", perfil.fecha_texto or ""),
        ("Días", str(perfil.dias_disponibles or "")),
        ("Nivel", nivel(perfil.nivel_preferido) if perfil.nivel_preferido else ""),
        ("Presupuesto", f"{usd(perfil.presupuesto_usd_pp)} por persona" if perfil.presupuesto_usd_pp else ""),
        ("Llega a Cusco", {"mismo_dia": "el mismo día del trek", "antes": "antes del trek"}.get(
            perfil.llega_a_cusco or "", "")),
        ("Idioma", idioma(perfil.idioma)),
    ]
    return [(k, v) for k, v in datos if v]


def html_perfil(perfil) -> str:
    fichas = "".join(f'<span class="ficha"><span class="ficha-dato">{escape(k)}</span>{escape(v)}</span>'
                     for k, v in fichas_perfil(perfil))
    faltan = "".join(f'<span class="etiqueta etiqueta-falta">Falta: {escape(f)}</span>'
                     for f in perfil.datos_faltantes)
    return f'<div class="fichas">{fichas}{faltan}</div>'


def html_opciones(opciones) -> str:
    filas = []
    for o in opciones:
        alternativa = '<span class="etiqueta etiqueta-alternativa">Alternativa</span>' if o.es_alternativa else ""
        personas = "1 persona" if o.personas == 1 else f"{o.personas} personas"
        filas.append(
            '<div class="opcion">'
            f'<div class="opcion-trek"><div class="opcion-nombre">{escape(o.trek)}{alternativa}</div>'
            f'<div class="opcion-meta">{o.dias} días · {escape(nivel(o.nivel))} · {personas}</div></div>'
            f'<div class="opcion-precio"><div><span class="precio">{usd(o.precio_pp)}</span>'
            '<span class="precio-unidad">por persona</span></div>'
            f'<div class="opcion-meta">Total {usd(o.total)} · Depósito {usd(o.deposito)}</div></div>'
            '</div>'
        )
    return f'<div class="opciones">{"".join(filas)}</div>'


def html_desglose(paquete) -> str:
    """Desglose del paquete para el vendedor: cada componente con su cálculo, totales, recargo y depósito."""
    p = paquete
    o = p.opcion
    grupo = "1 persona" if p.personas == 1 else f"{p.personas} personas"
    filas = [(f"{o.trek}, {o.dias} días, {nivel(o.nivel).lower()}", f"{usd(o.precio_pp)} × {grupo}", p.base_c)]
    for c in p.componentes:
        if c.unidad == "por grupo":
            calculo = f"{usd(c.precio_c / 100)} por grupo"
        elif c.unidad == "por noche":
            noches = "1 noche" if c.noches == 1 else f"{c.noches} noches"
            calculo = f"{usd(c.precio_c / 100)} × {noches} × {grupo}"
        else:
            calculo = f"{usd(c.precio_c / 100)} × {grupo}"
        filas.append((c.nombre, calculo, c.total_c))
    cuerpo = "".join(f'<tr><td>{escape(n)}<div class="desglose-calculo">{escape(k)}</div></td>'
                     f'<td class="desglose-monto">{usd(t / 100)}</td></tr>' for n, k, t in filas)
    pie = (f'<tr class="desglose-total"><td>Total del grupo<div class="desglose-calculo">'
           f'{usd(p.por_persona_c / 100)} por persona</div></td><td class="desglose-monto">{usd(p.subtotal_c / 100)}</td></tr>')
    if p.recargo_c:
        pie += (f'<tr><td>Recargo por pago con { {"tarjeta": "tarjeta", "paypal": "PayPal"}.get(p.metodo_pago, escape(p.metodo_pago))}'
                f'<div class="desglose-calculo">{p.porcentaje_recargo:g} % del total</div></td>'
                f'<td class="desglose-monto">{usd(p.recargo_c / 100)}</td></tr>'
                f'<tr class="desglose-total"><td>Total a pagar</td><td class="desglose-monto">{usd(p.total_c / 100)}</td></tr>')
    pie += (f'<tr><td>Depósito (50 %)<div class="desglose-calculo">Saldo {usd(p.saldo_c / 100)} hasta 30 días antes'
            f'</div></td><td class="desglose-monto">{usd(p.deposito_c / 100)}</td></tr>')
    return f'<table class="desglose"><tbody>{cuerpo}{pie}</tbody></table>'


# ---------------------------------------------------------------- Consulta en tres pasos
ICONO_FICHA = {"Trek": "hiking", "Personas": "group", "Mes del viaje": "calendar_month", "Fechas": "event",
               "Días": "schedule", "Nivel": "signal_cellular_alt", "Presupuesto": "payments",
               "Llega a Cusco": "flight_land", "Idioma": "translate"}


def icono(nombre: str) -> str:
    """Ícono Material como texto (la fuente la trae Streamlit); decorativo, no lo lee el lector de pantalla."""
    return f'<span class="ico" aria-hidden="true">{escape(nombre)}</span>'


def html_chips(perfil) -> str:
    """"Lo que entendimos del viajero": chips pequeños con ícono; lo que falta, como chip de aviso."""
    chips = "".join(f'<span class="chip" title="{escape(k)}">{icono(ICONO_FICHA.get(k, "label"))}{escape(v)}</span>'
                    for k, v in fichas_perfil(perfil))
    faltan = "".join(f'<span class="chip chip-falta">{icono("help")}Falta: {escape(f)}</span>'
                     for f in perfil.datos_faltantes)
    return f'<div class="chips">{chips}{faltan}</div>'


def html_opciones_compactas(opciones) -> str:
    """Cada opción en dos líneas: qué es y cuánto cuesta."""
    filas = []
    for o in opciones:
        alternativa = '<span class="etiqueta etiqueta-alternativa">Alternativa</span>' if o.es_alternativa else ""
        personas = "1 persona" if o.personas == 1 else f"{o.personas} personas"
        filas.append(
            '<div class="opcion-compacta">'
            f'<div class="opcion-linea">{escape(o.trek)}{alternativa}'
            f'<span class="opcion-meta"> · {o.dias} días · {escape(nivel(o.nivel))} · {personas}</span></div>'
            f'<div class="opcion-linea"><span class="precio-chico">{usd(o.precio_pp)}</span>'
            f'<span class="opcion-meta"> por persona · total {usd(o.total)} · depósito {usd(o.deposito)}</span></div>'
            '</div>')
    return f'<div class="opciones">{"".join(filas)}</div>'


# ---------------------------------------------------------------- Guía rápida ("¿Cómo se usa?")
# El mismo contenido está en docs/manual_consultas.md.
GUIA_PASOS = [
    ("content_paste", "Pega el mensaje del viajero tal como llegó."),
    ("edit_note", "Pulsa «Preparar respuesta»: verás el mensaje en su idioma con los precios de tu tarifario."),
    ("fact_check", "Revisa las advertencias y «Lo que entendimos», edita si hace falta y copia o abre WhatsApp: "
                   "ningún mensaje se envía solo."),
]
GUIA_NOTAS = [
    "Después marca la consulta como cotizada o reservada para que el Tablero aprenda.",
    "Si falta algo, la respuesta pide la fecha, el trek o el nivel.",
    "Si el modelo no responde se usa el de respaldo y luego un ejemplo guardado, y la app lo avisa.",
    "Para cambiar precios: Mi agencia.",
]
