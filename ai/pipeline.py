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
from core.cotizacion import (NO_REEMBOLSABLE_CAMINO_INCA_PP, NOMBRE_RUTA, OpcionCotizada, opciones_para_perfil,
                             treks_sin_precio)

AGENCIA = "Andes Trek Demo"
MAXIMO_OPCIONES = 2  # con 3 opciones y sus listas, el mensaje pasaba de 150 palabras


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


def nota_presupuesto(perfil, opciones: list[OpcionCotizada]) -> str | None:
    """Si el presupuesto del turista no alcanza para la opción más barata, el código lo dice."""
    presupuesto = getattr(perfil, "presupuesto_usd_pp", None)
    if not presupuesto or not opciones:
        return None
    mas_barata = min(o.precio_pp_con_extras for o in opciones)
    if presupuesto >= mas_barata:
        return None
    return (f"El presupuesto del turista (US$ {presupuesto:g} por persona) es menor que la opción más barata "
            f"de la cotización (US$ {mas_barata} por persona).")


def nota_trek_sin_precio(sin_precio: list[str], opciones: list[OpcionCotizada]) -> str | None:
    """Si el turista pidió un trek que no está en el tarifario, el código se lo dice al modelo."""
    if not sin_precio:
        return None
    nombres = " y ".join(NOMBRE_RUTA.get(t, t) for t in sin_precio)
    nota = f"El turista pidió {nombres}, que no está en el tarifario de la agencia: no hay precio para ese trek."
    alternativas = sorted({o.trek for o in opciones if o.es_alternativa})
    if alternativas:
        nota += f" Las opciones de la COTIZACIÓN ({', '.join(alternativas)}) son alternativas parecidas."
    return nota


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


def precios_permitidos(opciones: list[OpcionCotizada], perfil=None) -> set[int]:
    """Todos los montos que el código calculó y le pasó al modelo, más el presupuesto que dio el turista."""
    permitidos: set[int] = set()
    presupuesto = getattr(perfil, "presupuesto_usd_pp", None)
    if presupuesto:
        permitidos.add(int(presupuesto))
    for o in opciones:
        permitidos |= {o.precio_pp, o.precio_pp_con_extras, o.total, o.deposito, o.saldo}
        permitidos |= {precio for _, precio in o.extras}
        if o.requiere_permiso:
            permitidos.add(NO_REEMBOLSABLE_CAMINO_INCA_PP)
    return permitidos


def precios_no_autorizados(texto: str, opciones: list[OpcionCotizada], perfil=None) -> list[int]:
    """Montos del mensaje que no salen de la cotización: señal de que el modelo inventó un precio."""
    permitidos = precios_permitidos(opciones, perfil)
    return [m for m in precios_en_texto(texto) if m not in permitidos]


# Frases de la COTIZACIÓN y los avisos que, si aparecen tal cual, delatan que no se tradujeron.
# ("para reservar" no está: en portugués se escribe igual.)
_QUEDO_EN_ESPANOL = re.compile(r"\b(del total|hasta 30 días|por persona|no son reembolsables|cupo diario|no incluye|"
                               r"bolsa de dormir|guía bilingüe|tren de regreso|comidas durante)\b",
                               flags=re.IGNORECASE)

# Frases que prometen cupo. La cotización no sabe si hay cupo: solo el sistema oficial lo confirma.
_PROMETE_CUPO = re.compile(
    r"\b(hay cupos?|tenemos cupos?|hay disponibilidad|temos vagas?|tem vagas?|há vagas?|"
    r"we have (availability|spots|space)|there (is|are) (still )?(availability|spots|space)|"
    r"nous avons des places|wir haben (noch )?plätze)\b",
    flags=re.IGNORECASE,
)


# Montos que siguen a "depósito" o "saldo" (en los idiomas del demo), en la misma frase.
_CLAVES_DEPOSITO = r"deposits?|dep[óo]sitos?|anticipo|adelanto|sinal|acompte|anzahlung"
_CLAVES_SALDO = r"balance|saldo|restante|solde|restbetrag"
_DEPOSITO = re.compile(rf"\b(?:{_CLAVES_DEPOSITO})\b", flags=re.IGNORECASE)
_SALDO = re.compile(rf"\b(?:{_CLAVES_SALDO})\b", flags=re.IGNORECASE)
_MONTO_USD = re.compile(r"(?:US\$|USD|\$)\s?(\d{1,3}(?:[.,]\d{3})+|\d+)")
_FIN_FRASE = re.compile(r"[\n;]|\.\s|\.$")


def _montos(clave: re.Pattern, otra: re.Pattern, texto: str) -> list[int]:
    """Todos los montos en US$ desde la palabra clave hasta el fin de la frase o la otra palabra clave.
    Así "Deposit US$ 600 (4 days) or US$ 680 (5 days)" da [600, 680]."""
    montos = []
    for m in clave.finditer(texto):
        tramo = texto[m.end():m.end() + 80]
        for corte in (_FIN_FRASE.search(tramo), otra.search(tramo)):
            if corte:
                tramo = tramo[:corte.start()]
        montos += [int(re.sub(r"[.,]", "", x)) for x in _MONTO_USD.findall(tramo)]
    return montos


def revisar_deposito(texto: str, opciones: list[OpcionCotizada]) -> list[str]:
    """Advertencias si el depósito o el saldo no coinciden con ninguna opción, o si con varias
    opciones se da un solo depósito sin decir de cuál."""
    if not opciones:
        return []
    advertencias = []
    depositos, saldos = _montos(_DEPOSITO, _SALDO, texto), _montos(_SALDO, _DEPOSITO, texto)
    validos_deposito = {o.deposito for o in opciones}
    if any(o.requiere_permiso for o in opciones):
        validos_deposito.add(NO_REEMBOLSABLE_CAMINO_INCA_PP)  # "US$ 200 del depósito no son reembolsables"
    validos_saldo = {o.saldo for o in opciones}
    malos = sorted({d for d in depositos if d not in validos_deposito} | {s for s in saldos if s not in validos_saldo})
    if malos:
        esperados = ", ".join(f"US$ {o.deposito} / US$ {o.saldo}" for o in opciones)
        advertencias.append(f"El depósito o saldo del mensaje (US$ {', '.join(map(str, malos))}) no coincide con "
                            f"ninguna opción. Depósito / saldo de cada opción: {esperados}.")
    if len(opciones) > 1:
        cubiertas = {d for d in depositos if d in {o.deposito for o in opciones}}
        if 0 < len(cubiertas) < len(opciones) or (saldos and len(set(saldos)) < len(opciones)):
            advertencias.append("Con varias opciones, el mensaje da un solo depósito o saldo sin decir de cuál. "
                                "Di el de cada opción o escribe \"50 % del total de la opción elegida\".")
    return advertencias


# Palabras con las que el mensaje dice que una opción es alternativa (idiomas del demo).
_DICE_ALTERNATIVA = re.compile(
    r"alternativ|instead|similar|parecid|semelhante|en (?:su )?lugar|em vez|au lieu|à la place|"
    r"stattdessen|ähnlich", flags=re.IGNORECASE)


def revisar_alternativas(texto: str, opciones: list[OpcionCotizada]) -> list[str]:
    """Advertencia si el mensaje da el precio de una opción alternativa sin decir que lo es."""
    montos = set(precios_en_texto(texto))
    dadas = [o for o in opciones if o.es_alternativa and {o.precio_pp, o.precio_pp_con_extras, o.total} & montos]
    if not dadas or _DICE_ALTERNATIVA.search(texto):
        return []
    treks = ", ".join(dict.fromkeys(o.trek for o in dadas))
    return [f"El mensaje ofrece {treks} sin decir que es una alternativa a lo que pidió el viajero. "
            "Dilo claro (por ejemplo, \"como alternativa\")."]


def contar_palabras(texto: str) -> int:
    return len(texto.split())


def contar_lineas(texto: str) -> int:
    """Líneas con texto (las líneas en blanco no cuentan)."""
    return sum(1 for linea in texto.splitlines() if linea.strip())


def controlar_borrador(borrador: BorradorRespuesta, perfil: PerfilTurista,
                       opciones: list[OpcionCotizada]) -> tuple[list[int], list[str]]:
    """Revisa el borrador en código. Devuelve (precios no autorizados, advertencias)."""
    texto = borrador.mensaje_para_cliente
    advertencias = []
    no_autorizados = precios_no_autorizados(texto, opciones, perfil)
    if no_autorizados:
        advertencias.append(f"El mensaje tiene montos que no están en la cotización: {no_autorizados}. "
                            "Corrígelos antes de enviar.")
    if opciones and not precios_en_texto(texto):
        advertencias.append("El mensaje no dice el precio. Agrega el precio por persona y el total.")
    palabras = contar_palabras(texto)
    if palabras >= prompts.LIMITE_PALABRAS:
        advertencias.append(f"El mensaje tiene {palabras} palabras; debe tener menos de {prompts.LIMITE_PALABRAS}.")
    advertencias += revisar_deposito(texto, opciones)
    advertencias += revisar_alternativas(texto, opciones)
    lineas = contar_lineas(texto)
    if lineas < prompts.MINIMO_LINEAS:
        advertencias.append(f"El mensaje tiene {lineas} línea(s); sepáralo en al menos {prompts.MINIMO_LINEAS} "
                            "(saludo, opciones, qué incluye, depósito, preguntas) para que se lea bien en WhatsApp.")
    if borrador.idioma.lower() != perfil.idioma.lower():
        advertencias.append(f"El mensaje está en '{borrador.idioma}' y el turista escribió en '{perfil.idioma}'.")
    if perfil.idioma.lower() != "es" and _QUEDO_EN_ESPANOL.search(texto):
        advertencias.append("Parte del mensaje quedó en español (por ejemplo, la línea del depósito). Tradúcela.")
    if _PROMETE_CUPO.search(texto):
        advertencias.append("El mensaje parece prometer cupo o disponibilidad. Quítalo: se confirma en el sistema oficial.")
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
    opciones = opciones_para_perfil(perfil, tarifario, extras, maximo=MAXIMO_OPCIONES)
    fecha_posible = not any(o.motivo_alternativa == "no_disponible" for o in opciones)
    aviso = aviso_clave(perfil, opciones)
    presupuesto = nota_presupuesto(perfil, opciones)
    sin_precio = treks_sin_precio(perfil, tarifario)

    mensaje = prompts.mensaje_responder(
        consulta=consulta,
        perfil_json=perfil.model_dump_json(indent=2),
        cotizacion=texto_cotizacion(opciones),
        conocimiento="\n\n".join(f.para_prompt() for f in fragmentos),
        aviso=aviso,
        fecha_posible=fecha_posible,
        agencia=agencia,
        nota_presupuesto=presupuesto,
        nota_trek_sin_precio=nota_trek_sin_precio(sin_precio, opciones),
    )
    borrador, uso2 = llm.estructurado(prompts.SISTEMA_RESPONDER, mensaje, BorradorRespuesta)

    no_autorizados, advertencias = controlar_borrador(borrador, perfil, opciones)
    if sin_precio:
        nombres = " y ".join(NOMBRE_RUTA.get(t, t) for t in sin_precio)
        advertencias.insert(0, f"El viajero pidió {nombres}, que no está en tu tarifario: confírmale el precio.")
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
