"""Respuesta automática fuera de horario (modo nocturno), armada solo por código.

Pensado para reutilizarse en un webhook de la API de WhatsApp Cloud: hoy la app solo lo
SIMULA y no envía nada.

El mensaje no lo escribe el modelo: se arma con plantillas fijas en el idioma del viajero
(es, en, pt, fr, de; cualquier otro, en inglés) y con datos del tarifario:
  saludo · "desde US$ X por persona" (el menor precio del trek para su grupo) · qué incluye ·
  solo las preguntas que faltan (fecha exacta, número de personas) · cuándo responde un asesor.

Se enviaría solo si hay idioma y trek detectados, el trek tiene precio y ningún control del
código dio advertencia. Si no, queda en espera del vendedor y se usa un mensaje corto de
recepción, sin montos.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time

import pandas as pd

from ai.fecha import ZONA
from core.cotizacion import NOMBRE_RUTA, PERSONAS_POR_DEFECTO, precio_por_persona

APERTURA = time(8, 0)
CIERRE = time(20, 0)
IDIOMAS = ("es", "en", "pt", "fr", "de")
IDIOMA_POR_DEFECTO = "en"

TEXTOS = {
    "es": {"saludo": "¡Hola! Gracias por escribir a {agencia}.", "desde": "{trek}: desde US$ {precio} por persona.",
           "sin_precio": "Recibimos tu consulta sobre {trek}.", "incluye": "Incluye: {items}.",
           "fecha": "¿Qué fecha exacta tienes en mente?", "personas": "¿Cuántas personas viajan?",
           "asesor": "Un asesor te confirma disponibilidad y precio final desde las {hora} (hora de Perú).",
           "recepcion": "Recibimos tu mensaje. Un asesor te responde desde las {hora} (hora de Perú)."},
    "en": {"saludo": "Hi! Thanks for writing to {agencia}.", "desde": "{trek}: from US$ {precio} per person.",
           "sin_precio": "We received your inquiry about {trek}.", "incluye": "Includes: {items}.",
           "fecha": "What exact date do you have in mind?", "personas": "How many people are traveling?",
           "asesor": "An advisor will confirm availability and the final price from {hora} (Peru time).",
           "recepcion": "We received your message. An advisor will reply from {hora} (Peru time)."},
    "pt": {"saludo": "Olá! Obrigado por escrever para a {agencia}.", "desde": "{trek}: a partir de US$ {precio} por pessoa.",
           "sin_precio": "Recebemos sua consulta sobre {trek}.", "incluye": "Inclui: {items}.",
           "fecha": "Qual data exata você tem em mente?", "personas": "Quantas pessoas vão viajar?",
           "asesor": "Um consultor confirma a disponibilidade e o preço final a partir das {hora} (horário do Peru).",
           "recepcion": "Recebemos sua mensagem. Um consultor responde a partir das {hora} (horário do Peru)."},
    "fr": {"saludo": "Bonjour ! Merci d'avoir écrit à {agencia}.", "desde": "{trek} : à partir de US$ {precio} par personne.",
           "sin_precio": "Nous avons bien reçu votre demande sur {trek}.", "incluye": "Comprend : {items}.",
           "fecha": "Quelle date exacte envisagez-vous ?", "personas": "Combien de personnes voyagent ?",
           "asesor": "Un conseiller vous confirme la disponibilité et le prix final à partir de {hora} (heure du Pérou).",
           "recepcion": "Nous avons bien reçu votre message. Un conseiller vous répond à partir de {hora} (heure du Pérou)."},
    "de": {"saludo": "Hallo! Danke für Ihre Nachricht an {agencia}.", "desde": "{trek}: ab US$ {precio} pro Person.",
           "sin_precio": "Wir haben Ihre Anfrage zu {trek} erhalten.", "incluye": "Inklusive: {items}.",
           "fecha": "An welches genaue Datum denken Sie?", "personas": "Wie viele Personen reisen?",
           "asesor": "Ein Berater bestätigt Verfügbarkeit und Endpreis ab {hora} (peruanische Zeit).",
           "recepcion": "Wir haben Ihre Nachricht erhalten. Ein Berater antwortet ab {hora} (peruanische Zeit)."},
}

NOMBRE_TREK = {  # solo los que cambian según el idioma; el resto usa NOMBRE_RUTA
    "camino_inca": {"es": "Camino Inca clásico", "en": "classic Inca Trail", "pt": "Trilha Inca clássica",
                    "fr": "Chemin de l'Inca classique", "de": "klassischer Inkapfad"},
    "camino_inca_corto": {"es": "Camino Inca corto", "en": "short Inca Trail", "pt": "Trilha Inca curta",
                          "fr": "Chemin de l'Inca court", "de": "kurzer Inkapfad"},
}

# Lo que incluye el tarifario demo, traducido. Un elemento sin traducción no se muestra:
# es preferible omitirlo a dejarlo en español en un mensaje que nadie revisa.
INCLUYE = {
    "guía bilingüe": ("bilingual guide", "guia bilíngue", "guide bilingue", "zweisprachiger Guide"),
    "transporte de ida": ("transport to the trailhead", "transporte de ida", "transport aller", "Hinfahrt"),
    "transporte ida y vuelta desde cusco": ("round-trip transport from Cusco", "transporte de ida e volta desde Cusco",
                                            "transport aller-retour depuis Cusco", "Hin- und Rückfahrt ab Cusco"),
    "comidas durante el trek": ("meals during the trek", "refeições durante o trekking", "repas pendant le trek",
                                "Mahlzeiten während des Treks"),
    "entrada a machu picchu": ("Machu Picchu entrance", "entrada em Machu Picchu", "entrée au Machu Picchu",
                               "Eintritt Machu Picchu"),
    "tren de regreso a ollantaytambo": ("return train to Ollantaytambo", "trem de volta a Ollantaytambo",
                                        "train retour à Ollantaytambo", "Rückfahrt mit dem Zug nach Ollantaytambo"),
    "permiso del camino inca": ("Inca Trail permit", "permissão da Trilha Inca", "permis du Chemin de l'Inca",
                                "Inka-Trail-Genehmigung"),
    "porteadores": ("porters", "carregadores", "porteurs", "Träger"),
    "tren al km 104": ("train to KM 104", "trem até o KM 104", "train jusqu'au KM 104", "Zug bis KM 104"),
    "almuerzo del día de caminata": ("lunch on the hiking day", "almoço no dia da caminhada", "déjeuner le jour de marche",
                                     "Mittagessen am Wandertag"),
    "entrada al sitio arqueológico de choquequirao": (
        "entrance to the Choquequirao archaeological site", "entrada no sítio arqueológico de Choquequirao",
        "entrée au site archéologique de Choquequirao", "Eintritt zur Ausgrabungsstätte Choquequirao"),
    "1 noche en aguas calientes": ("1 night in Aguas Calientes", "1 noite em Aguas Calientes", "1 nuit à Aguas Calientes",
                                   "1 Nacht in Aguas Calientes"),
    "bicicleta y casco para la bajada": ("bike and helmet for the downhill ride", "bicicleta e capacete para a descida",
                                         "vélo et casque pour la descente", "Fahrrad und Helm für die Abfahrt"),
}
_POSICION = {"en": 0, "pt": 1, "fr": 2, "de": 3}

EN_ESPERA = "Queda en espera del vendedor"
SE_ENVIARIA = "Se enviaría sola"


@dataclass
class RespuestaNocturna:
    idioma: str                  # idioma del mensaje (es, en, pt, fr o de)
    mensaje: str                 # lo que se enviaría: la respuesta segura o, si queda en espera, la de recepción
    se_enviaria_sola: bool
    motivos: list[str] = field(default_factory=list)  # por qué queda en espera (para el vendedor, en español)
    mensaje_completo: str = ""   # la respuesta segura, aunque quede en espera

    @property
    def estado(self) -> str:
        return SE_ENVIARIA if self.se_enviaria_sola else EN_ESPERA


# --- Horario -------------------------------------------------------------------

def en_lima(momento: datetime) -> datetime:
    """La hora en Lima. Una hora sin zona se toma como hora de Lima."""
    return momento.replace(tzinfo=ZONA) if momento.tzinfo is None else momento.astimezone(ZONA)


def fuera_de_horario(momento: datetime, apertura: time = APERTURA, cierre: time = CIERRE) -> bool:
    """True si la consulta llega fuera del horario de atención (evaluado en hora de Lima)."""
    hora = en_lima(momento).time()
    return not (apertura <= hora < cierre)


def hora_en_texto(hora: time, idioma: str) -> str:
    minutos = f"{hora.minute:02d}"
    if idioma == "es":
        h12 = hora.hour % 12 or 12
        return f"{h12}:{minutos} {'a. m.' if hora.hour < 12 else 'p. m.'}"
    if idioma == "en":
        h12 = hora.hour % 12 or 12
        return f"{h12}:{minutos} {'a.m.' if hora.hour < 12 else 'p.m.'}"
    if idioma == "pt":
        return f"{hora.hour}h" + (minutos if hora.minute else "")
    if idioma == "fr":
        return f"{hora.hour} h" + (f" {minutos}" if hora.minute else "")
    return f"{hora.hour}:{minutos} Uhr"


# --- Datos del tarifario ---------------------------------------------------------

def idioma_de_respuesta(idioma: str | None) -> str:
    codigo = (idioma or "").lower()
    return codigo if codigo in IDIOMAS else IDIOMA_POR_DEFECTO


def precio_desde(trek: str, tarifario: pd.DataFrame, personas: int | None = None) -> int | None:
    """El menor precio por persona del trek para ese tamaño de grupo (cualquier nivel y duración).
    None si el trek no está en el tarifario o ninguna fila admite al grupo."""
    personas = personas or PERSONAS_POR_DEFECTO
    filas = tarifario[(tarifario["ruta"] == trek) & (tarifario["tamano_max_grupo"] >= personas)]
    if filas.empty:
        return None
    return int(min(precio_por_persona(f, personas) for _, f in filas.iterrows()))


def incluye_comun(trek: str, tarifario: pd.DataFrame) -> list[str]:
    """Lo que incluyen TODOS los niveles del trek (lo que el viajero recibe en cualquier caso)."""
    listas = [[x.strip() for x in str(s).split(";") if x.strip()]
              for s in tarifario.loc[tarifario["ruta"] == trek, "incluye"]]
    if not listas:
        return []
    otras = [{x.lower() for x in lista} for lista in listas[1:]]
    return [x for x in listas[0] if all(x.lower() in o for o in otras)]


def traducir_incluye(items: list[str], idioma: str) -> list[str]:
    if idioma == "es":
        return [items[0][:1].lower() + items[0][1:]] + items[1:] if items else []
    return [INCLUYE[x.lower()][_POSICION[idioma]] for x in items if x.lower() in INCLUYE]


def nombre_trek(trek: str, idioma: str) -> str:
    return NOMBRE_TREK.get(trek, {}).get(idioma) or NOMBRE_RUTA.get(trek, trek)


def _mayuscula(texto: str) -> str:
    return texto[:1].upper() + texto[1:]


# --- Respuesta ---------------------------------------------------------------------

def advertencias_de_control(resultado) -> list[str]:
    """Las advertencias de los controles del código, sin las notas que el modelo deja para la agencia."""
    del_modelo = set(resultado.borrador.advertencias_para_agencia)
    return [a for a in resultado.advertencias if a not in del_modelo]


def mensaje_seguro(perfil, tarifario: pd.DataFrame, agencia: str, apertura: time = APERTURA) -> str:
    """La primera respuesta, armada por código. Sin monto si el trek no tiene precio."""
    idioma = idioma_de_respuesta(perfil.idioma)
    t = TEXTOS[idioma]
    lineas = [t["saludo"].format(agencia=agencia)]
    trek = perfil.treks_de_interes[0] if perfil.treks_de_interes else None
    if trek:
        nombre = nombre_trek(trek, idioma)
        precio = precio_desde(trek, tarifario, perfil.num_personas)
        if precio is not None:
            lineas.append(t["desde"].format(trek=_mayuscula(nombre), precio=precio))
            items = traducir_incluye(incluye_comun(trek, tarifario), idioma)
            if items:
                lineas.append(t["incluye"].format(items=", ".join(items)))
        else:
            lineas.append(t["sin_precio"].format(trek=nombre))
    if "fecha exacta" in perfil.datos_faltantes or not perfil.fecha_texto:
        lineas.append(t["fecha"])
    if not perfil.num_personas:
        lineas.append(t["personas"])
    lineas.append(t["asesor"].format(hora=hora_en_texto(apertura, idioma)))
    return "\n".join(lineas)


def mensaje_recepcion(perfil, agencia: str, apertura: time = APERTURA) -> str:
    """Acuse de recibo corto y sin montos, para cuando la respuesta queda en espera del vendedor."""
    idioma = idioma_de_respuesta(perfil.idioma)
    t = TEXTOS[idioma]
    return t["saludo"].format(agencia=agencia) + "\n" + t["recepcion"].format(hora=hora_en_texto(apertura, idioma))


def respuesta_nocturna(perfil, tarifario: pd.DataFrame, advertencias_control: list[str], agencia: str,
                       apertura: time = APERTURA) -> RespuestaNocturna:
    motivos = []
    if not perfil.idioma:
        motivos.append("No se detectó el idioma del viajero.")
    if not perfil.treks_de_interes:
        motivos.append("No se detectó qué trek le interesa.")
    elif precio_desde(perfil.treks_de_interes[0], tarifario, perfil.num_personas) is None:
        motivos.append(f"{NOMBRE_RUTA.get(perfil.treks_de_interes[0], perfil.treks_de_interes[0])} "
                       "no tiene precio en tu tarifario para ese grupo.")
    if advertencias_control:
        motivos.append("El control dio advertencias: " + " ".join(advertencias_control))
    completo = mensaje_seguro(perfil, tarifario, agencia, apertura)
    enviable = not motivos
    return RespuestaNocturna(
        idioma=idioma_de_respuesta(perfil.idioma),
        mensaje=completo if enviable else mensaje_recepcion(perfil, agencia, apertura),
        se_enviaria_sola=enviable,
        motivos=motivos,
        mensaje_completo=completo,
    )
