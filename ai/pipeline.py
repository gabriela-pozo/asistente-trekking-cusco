"""Flujo principal: consulta -> perfil -> conocimiento -> cotización -> borrador -> controles.

1. El modelo extrae el perfil del turista (salida estructurada PerfilTurista).
2. Se buscan los fragmentos de la base de conocimiento (ai/knowledge.py, TF-IDF).
3. El código cotiza con el tarifario (core/cotizacion.py). El modelo no calcula precios.
4. El modelo redacta el borrador con esos datos (salida estructurada BorradorRespuesta).
5. Controles en código: precios que no salen de la cotización, largo, idioma y preguntas.
   No bloquean nada: quedan como advertencias para el vendedor, que revisa antes de enviar.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

import pandas as pd

from ai import prompts
from ai.knowledge import MESES_DE_LLUVIA, BaseConocimiento, Fragmento, archivos_desde_perfil, consulta_desde_perfil
from ai.llm import LLM, Uso
from ai.schemas import BorradorRespuesta, PerfilTurista
from core.cotizacion import NO_REEMBOLSABLE_CAMINO_INCA_PP, OpcionCotizada, opciones_para_perfil

AGENCIA = "Andes Trek Demo"


@dataclass
class Resultado:
    perfil: PerfilTurista
    opciones: list[OpcionCotizada]
    fragmentos: list[Fragmento]
    aviso: str | None
    borrador: BorradorRespuesta
    precios_no_autorizados: list[int]
    advertencias: list[str] = field(default_factory=list)  # las del modelo + las de los controles
    uso: Uso = field(default_factory=Uso)


# --- Avisos ------------------------------------------------------------------

def aviso_clave(perfil, opciones: list[OpcionCotizada]) -> str | None:
    """El aviso más importante para este caso (uno solo, decidido por el código)."""
    if any(o.requiere_permiso for o in opciones):
        return ("Los permisos del Camino Inca tienen cupo diario, son nominales y no reembolsables: "
                "solo se confirman al comprarlos.")
    if getattr(perfil, "mes_viaje", None) in MESES_DE_LLUVIA:
        return "Ese mes es temporada de lluvias en Cusco: hay que llevar ropa impermeable y los caminos pueden estar con barro."
    if opciones:
        return ("La entrada a Machu Picchu es nominal y solo queda confirmada cuando la agencia la compra "
                "en el sistema oficial.")
    return None


# --- Controles sobre el borrador ----------------------------------------------

_MONTO = re.compile(
    r"(?:US\$|USD|\$)\s?(\d{1,3}(?:[.,\s]\d{3})+|\d+)"          # US$ 1,360 / $680 / USD 680
    r"|(\d{1,3}(?:[.,\s]\d{3})+|\d+)\s?(?:USD|US\$|dólares|dollars|dólar|dollar)",  # 680 USD / 680 dólares
    flags=re.IGNORECASE,
)


def precios_en_texto(texto: str) -> list[int]:
    """Montos en dólares escritos en el mensaje: US$ 680, $1,360, 1.360 USD, 680 dollars."""
    montos = []
    for a, b in _MONTO.findall(texto):
        crudo = re.sub(r"[.,\s]", "", a or b)
        if crudo:
            montos.append(int(crudo))
    return montos


def precios_permitidos(opciones: list[OpcionCotizada]) -> set[int]:
    """Todos los montos que el código calculó y le pasó al modelo."""
    permitidos: set[int] = set()
    for o in opciones:
        permitidos |= {o.precio_pp, o.precio_pp_con_extras, o.total, o.deposito, o.saldo}
        permitidos |= {precio for _, precio in o.extras}
        if o.requiere_permiso:
            permitidos.add(NO_REEMBOLSABLE_CAMINO_INCA_PP)
    return permitidos


def precios_no_autorizados(texto: str, opciones: list[OpcionCotizada]) -> list[int]:
    """Montos del mensaje que no salen de la cotización: señal de que el modelo inventó un precio."""
    permitidos = precios_permitidos(opciones)
    return [m for m in precios_en_texto(texto) if m not in permitidos]


def contar_palabras(texto: str) -> int:
    return len(texto.split())


def controlar_borrador(borrador: BorradorRespuesta, perfil: PerfilTurista,
                       opciones: list[OpcionCotizada]) -> tuple[list[int], list[str]]:
    """Revisa el borrador en código. Devuelve (precios no autorizados, advertencias)."""
    texto = borrador.mensaje_para_cliente
    advertencias = []
    no_autorizados = precios_no_autorizados(texto, opciones)
    if no_autorizados:
        advertencias.append(f"El mensaje tiene montos que no están en la cotización: {no_autorizados}. "
                            "Corrígelos antes de enviar.")
    if opciones and not precios_en_texto(texto):
        advertencias.append("El mensaje no dice el precio. Agrega el precio por persona y el total.")
    palabras = contar_palabras(texto)
    if palabras >= prompts.LIMITE_PALABRAS:
        advertencias.append(f"El mensaje tiene {palabras} palabras; debe tener menos de {prompts.LIMITE_PALABRAS}.")
    if borrador.idioma.lower() != perfil.idioma.lower():
        advertencias.append(f"El mensaje está en '{borrador.idioma}' y el turista escribió en '{perfil.idioma}'.")
    if not borrador.preguntas_al_turista:
        advertencias.append("El mensaje no termina con una pregunta al turista.")
    return no_autorizados, advertencias


# --- Flujo --------------------------------------------------------------------

def texto_cotizacion(opciones: list[OpcionCotizada]) -> str:
    return "\n".join(f"- {o.resumen()}" for o in opciones) or "Sin opciones en el tarifario: la agencia confirmará."


def procesar_consulta(consulta: str, llm: LLM, base: BaseConocimiento, tarifario: pd.DataFrame,
                      extras: pd.DataFrame | None = None, agencia: str = AGENCIA) -> Resultado:
    perfil, uso1 = llm.estructurado(prompts.SISTEMA_EXTRAER, consulta, PerfilTurista)

    fragmentos = base.buscar(consulta_desde_perfil(perfil), k=8, archivos_prioritarios=archivos_desde_perfil(perfil))
    opciones = opciones_para_perfil(perfil, tarifario, extras)
    fecha_posible = not any(o.es_alternativa for o in opciones)
    aviso = aviso_clave(perfil, opciones)

    mensaje = prompts.mensaje_responder(
        consulta=consulta,
        perfil_json=perfil.model_dump_json(indent=2),
        cotizacion=texto_cotizacion(opciones),
        conocimiento="\n\n".join(f.para_prompt() for f in fragmentos),
        aviso=aviso,
        fecha_posible=fecha_posible,
        agencia=agencia,
    )
    borrador, uso2 = llm.estructurado(prompts.SISTEMA_RESPONDER, mensaje, BorradorRespuesta)

    no_autorizados, advertencias = controlar_borrador(borrador, perfil, opciones)
    return Resultado(
        perfil=perfil,
        opciones=opciones,
        fragmentos=fragmentos,
        aviso=aviso,
        borrador=borrador,
        precios_no_autorizados=no_autorizados,
        advertencias=borrador.advertencias_para_agencia + advertencias,
        uso=uso1.sumar(uso2),
    )
