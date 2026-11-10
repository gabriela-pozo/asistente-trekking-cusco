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
EXTRAS = {"huayna_picchu": "Huayna Picchu", "vistadome": "Tren Vistadome"}

# Advertencias que impiden enviar el mensaje tal cual (van en rojo y arriba).
_GRAVES = ("no están en la cotización", "no está en tu tarifario", "no coincide", "no dice el precio")


def idioma(codigo: str | None) -> str:
    return IDIOMAS.get((codigo or "").lower(), (codigo or "").upper())


def mes(numero: int | None) -> str:
    return MESES[numero - 1] if numero and 1 <= numero <= 12 else ""


def nivel(codigo: str | None) -> str:
    return NOMBRE_NIVEL.get(codigo or "", codigo or "").capitalize()


def usd(monto: float | int) -> str:
    """1200 -> 'US$ 1 200' (espacio fino que no se separa entre miles)."""
    return "US$ " + f"{int(round(monto)):,}".replace(",", " ")


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
        ("Extras", ", ".join(EXTRAS.get(e, e) for e in perfil.extras_de_interes)),
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
        extras = (f" · incluye {escape(', '.join(n for n, _ in o.extras))}" if o.extras else "")
        personas = "1 persona" if o.personas == 1 else f"{o.personas} personas"
        filas.append(
            '<div class="opcion">'
            f'<div class="opcion-trek"><div class="opcion-nombre">{escape(o.trek)}{alternativa}</div>'
            f'<div class="opcion-meta">{o.dias} días · {escape(nivel(o.nivel))} · {personas}{extras}</div></div>'
            f'<div class="opcion-precio"><div><span class="precio">{usd(o.precio_pp_con_extras)}</span>'
            '<span class="precio-unidad">por persona</span></div>'
            f'<div class="opcion-meta">Total {usd(o.total)} · Depósito {usd(o.deposito)}</div></div>'
            '</div>'
        )
    return f'<div class="opciones">{"".join(filas)}</div>'
