"""Armar paquete: precio base del trek + extras opcionales + días en Cusco + recargo por forma de pago.

Así cotizan las agencias de Cusco (docs/research/cliente_misterioso.md): un precio base y
aparte la bolsa de dormir, los bastones, Huayna Picchu, el recargo con tarjeta, etc.

Todo lo calcula este código, en centavos para no arrastrar errores de redondeo. El modelo
solo sugiere qué extras ofrecer (y por qué); el vendedor marca o desmarca.

Unidades de los extras (data/extras_demo.csv, editable en "Mi agencia"):
  por persona  -> precio x personas
  por noche    -> precio x personas x noches. Para el hotel en Cusco, las noches en Cusco;
                  para la habitación individual, las noches de todo el viaje
                  (noches en Cusco + noches del trek, que son los días menos 1)
  por grupo    -> precio una vez, se reparte entre las personas
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from core.cotizacion import PORCENTAJE_DEPOSITO, OpcionCotizada

UNIDADES = ("por persona", "por noche", "por grupo")
MODULO = "modulo_cusco"          # valor de aplica_a de las filas del módulo de días en Cusco
HOTEL = {3: "hotel_cusco_3", 4: "hotel_cusco_4"}
TRASLADO = "traslado_aeropuerto"
MAXIMO_SUGERIDOS = 3

# Formas de pago y recargo por defecto (%). Agencia A del cliente misterioso: 5 % con tarjeta y 8 % con PayPal.
METODOS = {"transferencia": "Transferencia o efectivo", "tarjeta": "Tarjeta", "paypal": "PayPal"}
RECARGOS = {"transferencia": 0.0, "tarjeta": 5.0, "paypal": 8.0}


# --- Datos de los extras ------------------------------------------------------

def centavos(dolares: float) -> int:
    return int(round(float(dolares) * 100))


def aplica(extra: pd.Series, fila_trek: pd.Series | dict) -> bool:
    """aplica_a: 'todos', 'machu_picchu' (treks que llegan a Machu Picchu) o rutas separadas por ';'."""
    valores = {v.strip() for v in str(extra["aplica_a"]).split(";") if v.strip()}
    if MODULO in valores:
        return False
    if "todos" in valores:
        return True
    if "machu_picchu" in valores and str(fila_trek.get("llega_a_machu_picchu", "si")) != "no":
        return True
    return fila_trek["ruta"] in valores


def extras_aplicables(extras: pd.DataFrame, fila_trek) -> pd.DataFrame:
    """Los extras que se pueden ofrecer con ese trek (sin las filas del módulo de Cusco)."""
    if extras is None or extras.empty:
        return pd.DataFrame(columns=["extra_id", "extra", "unidad", "precio_usd", "aplica_a"])
    return extras[extras.apply(lambda e: aplica(e, fila_trek), axis=1)]


def fila_del_trek(opcion: OpcionCotizada, tarifario: pd.DataFrame) -> pd.Series:
    filas = tarifario[(tarifario["trek_id"] == opcion.trek_id) & (tarifario["nivel"] == opcion.nivel)]
    if filas.empty:
        filas = tarifario[tarifario["trek_id"] == opcion.trek_id]
    return filas.iloc[0]


def sugeridos_validos(sugeridos, extras: pd.DataFrame, fila_trek) -> list:
    """Lo que sugirió el modelo, solo si está en la lista de la agencia y aplica al trek. Máximo 3, sin repetir."""
    validos = set(extras_aplicables(extras, fila_trek)["extra_id"])
    vistos, salida = set(), []
    for s in sugeridos or []:
        if s.extra_id in validos and s.extra_id not in vistos:
            vistos.add(s.extra_id)
            salida.append(s)
    return salida[:MAXIMO_SUGERIDOS]


def noches_sugeridas(perfil) -> int:
    """1 noche en Cusco si llega el mismo día del trek o no dice cuándo llega (para aclimatarse); si no, 0."""
    return 0 if getattr(perfil, "llega_a_cusco", None) == "antes" else 1


# --- Paquete -------------------------------------------------------------------

@dataclass
class Seleccion:
    """Lo que marca el vendedor."""
    base: int = 0                          # índice de la opción del tarifario
    extras: list[str] = field(default_factory=list)
    noches_cusco: int = 0                  # 0, 1 o 2
    estrellas: int = 3                     # hotel 3★ o 4★
    metodo_pago: str = "transferencia"


@dataclass
class Componente:
    id: str
    nombre: str
    unidad: str
    precio_c: int        # precio unitario en centavos
    veces: int           # cuántas veces se cobra (personas, personas x noches o 1)
    beneficio: str = ""  # en español, para el vendedor
    noches: int = 0

    @property
    def total_c(self) -> int:
        return self.precio_c * self.veces


@dataclass
class Paquete:
    opcion: OpcionCotizada
    personas: int
    extras: list[Componente]            # los elegidos
    modulo: list[Componente]            # hotel y traslado (vacío si 0 noches)
    opcionales: list[Componente]        # los extras aplicables no elegidos
    noches_cusco: int
    estrellas: int
    metodo_pago: str
    porcentaje_recargo: float

    @property
    def componentes(self) -> list[Componente]:
        return self.modulo + self.extras

    @property
    def base_c(self) -> int:
        return self.opcion.precio_pp * 100 * self.personas

    @property
    def subtotal_c(self) -> int:
        return self.base_c + sum(c.total_c for c in self.componentes)

    @property
    def por_persona_c(self) -> int:
        return int(round(self.subtotal_c / self.personas))

    @property
    def recargo_c(self) -> int:
        return int(round(self.subtotal_c * self.porcentaje_recargo / 100))

    @property
    def total_c(self) -> int:
        return self.subtotal_c + self.recargo_c

    @property
    def deposito_c(self) -> int:
        return int(round(self.total_c * PORCENTAJE_DEPOSITO))

    @property
    def saldo_c(self) -> int:
        return self.total_c - self.deposito_c

    def montos(self) -> set[float]:
        """Todos los montos (en dólares) que el código calculó para este paquete: el control acepta solo estos."""
        cents = {self.opcion.precio_pp * 100, self.base_c, self.subtotal_c, self.por_persona_c, self.recargo_c,
                 self.total_c, self.deposito_c, self.saldo_c}
        for c in self.componentes + self.opcionales:
            cents |= {c.precio_c, c.total_c, int(round(c.total_c / self.personas))}
        return {c / 100 for c in cents if c}


def _componente(extra: pd.Series, personas: int, noches: int = 0) -> Componente:
    unidad = str(extra["unidad"]).strip()
    if unidad not in UNIDADES:
        raise ValueError(f"Unidad desconocida en el extra {extra['extra_id']}: {unidad!r}. Usa {', '.join(UNIDADES)}.")
    veces = {"por persona": personas, "por noche": personas * noches, "por grupo": 1}[unidad]
    beneficio = extra.get("beneficio_para_el_viajero", "")
    return Componente(id=str(extra["extra_id"]), nombre=str(extra["extra"]), unidad=unidad,
                      precio_c=centavos(extra["precio_usd"]), veces=veces,
                      beneficio="" if pd.isna(beneficio) else str(beneficio), noches=noches)


def armar_paquete(opciones: list[OpcionCotizada], tarifario: pd.DataFrame, extras: pd.DataFrame,
                  seleccion: Seleccion, recargos: dict[str, float] | None = None) -> Paquete | None:
    if not opciones:
        return None
    opcion = opciones[min(seleccion.base, len(opciones) - 1)]
    personas = opcion.personas
    fila = fila_del_trek(opcion, tarifario)
    noches_viaje = seleccion.noches_cusco + max(opcion.dias - 1, 0)
    elegidos, opcionales = [], []
    for _, e in extras_aplicables(extras, fila).iterrows():
        noches = noches_viaje if str(e["unidad"]).strip() == "por noche" else 0
        (elegidos if e["extra_id"] in seleccion.extras else opcionales).append(_componente(e, personas, noches))
    modulo = []
    if seleccion.noches_cusco > 0 and extras is not None:
        por_id = {str(e["extra_id"]): e for _, e in extras.iterrows()}
        if HOTEL.get(seleccion.estrellas) in por_id:
            modulo.append(_componente(por_id[HOTEL[seleccion.estrellas]], personas, seleccion.noches_cusco))
        if TRASLADO in por_id:
            modulo.append(_componente(por_id[TRASLADO], personas))
    porcentaje = (recargos or RECARGOS).get(seleccion.metodo_pago, 0.0)
    return Paquete(opcion=opcion, personas=personas, extras=elegidos, modulo=modulo, opcionales=opcionales,
                   noches_cusco=seleccion.noches_cusco, estrellas=seleccion.estrellas,
                   metodo_pago=seleccion.metodo_pago, porcentaje_recargo=float(porcentaje))


# --- Texto del paquete para el viajero (5 idiomas; otro idioma, en inglés) -------------

IDIOMAS = ("es", "en", "pt", "fr", "de")

FRASES = {
    "es": {"titulo": "Tu paquete para {grupo}:", "persona": "1 persona", "personas": "{n} personas",
           "trek": "{trek}, {dias} días, {nivel}", "pp": "por persona", "grupo": "por el grupo", "noche": "por noche",
           "noches": {1: "1 noche", 2: "2 noches"}, "total": "Total: US$ {pp} por persona, US$ {total} por el grupo.",
           "recargo": "Pago con {metodo}: +{pct} % (US$ {recargo}). Total a pagar: US$ {total}.",
           "deposito": "Depósito US$ {deposito} (50 %) para reservar; saldo US$ {saldo} hasta 30 días antes del trek.",
           "opcional": "Opcional: {lista}.", "otra": "Otra opción: {opcion}: US$ {precio} por persona.",
           "alternativa": "alternativa", "tarjeta": "tarjeta", "paypal": "PayPal",
           "nivel": {"economico": "económico", "estandar": "estándar", "premium": "premium"}},
    "en": {"titulo": "Your package for {grupo}:", "persona": "1 person", "personas": "{n} people",
           "trek": "{trek}, {dias} days, {nivel}", "pp": "per person", "grupo": "for the group", "noche": "per night",
           "noches": {1: "1 night", 2: "2 nights"}, "total": "Total: US$ {pp} per person, US$ {total} for the group.",
           "recargo": "Paying by {metodo}: +{pct} % (US$ {recargo}). Total to pay: US$ {total}.",
           "deposito": "Deposit US$ {deposito} (50 %) to book; balance US$ {saldo} up to 30 days before the trek.",
           "opcional": "Optional: {lista}.", "otra": "Another option: {opcion}: US$ {precio} per person.",
           "alternativa": "alternative", "tarjeta": "card", "paypal": "PayPal",
           "nivel": {"economico": "economy", "estandar": "standard", "premium": "premium"}},
    "pt": {"titulo": "Seu pacote para {grupo}:", "persona": "1 pessoa", "personas": "{n} pessoas",
           "trek": "{trek}, {dias} dias, {nivel}", "pp": "por pessoa", "grupo": "pelo grupo", "noche": "por noite",
           "noches": {1: "1 noite", 2: "2 noites"}, "total": "Total: US$ {pp} por pessoa, US$ {total} pelo grupo.",
           "recargo": "Pagamento com {metodo}: +{pct} % (US$ {recargo}). Total a pagar: US$ {total}.",
           "deposito": "Sinal de US$ {deposito} (50 %) para reservar; restante de US$ {saldo} até 30 dias antes do trekking.",
           "opcional": "Opcional: {lista}.", "otra": "Outra opção: {opcion}: US$ {precio} por pessoa.",
           "alternativa": "alternativa", "tarjeta": "cartão", "paypal": "PayPal",
           "nivel": {"economico": "econômico", "estandar": "padrão", "premium": "premium"}},
    "fr": {"titulo": "Votre forfait pour {grupo} :", "persona": "1 personne", "personas": "{n} personnes",
           "trek": "{trek}, {dias} jours, {nivel}", "pp": "par personne", "grupo": "pour le groupe", "noche": "par nuit",
           "noches": {1: "1 nuit", 2: "2 nuits"},
           "total": "Total : US$ {pp} par personne, US$ {total} pour le groupe.",
           "recargo": "Paiement par {metodo} : +{pct} % (US$ {recargo}). Total à payer : US$ {total}.",
           "deposito": "Acompte de US$ {deposito} (50 %) pour réserver ; solde de US$ {saldo} jusqu'à 30 jours avant le trek.",
           "opcional": "En option : {lista}.", "otra": "Autre option : {opcion} : US$ {precio} par personne.",
           "alternativa": "alternative", "tarjeta": "carte", "paypal": "PayPal",
           "nivel": {"economico": "économique", "estandar": "standard", "premium": "premium"}},
    "de": {"titulo": "Ihr Paket für {grupo}:", "persona": "1 Person", "personas": "{n} Personen",
           "trek": "{trek}, {dias} Tage, {nivel}", "pp": "pro Person", "grupo": "für die Gruppe", "noche": "pro Nacht",
           "noches": {1: "1 Nacht", 2: "2 Nächte"},
           "total": "Gesamt: US$ {pp} pro Person, US$ {total} für die Gruppe.",
           "recargo": "Zahlung per {metodo}: +{pct} % (US$ {recargo}). Zu zahlen: US$ {total}.",
           "deposito": "Anzahlung US$ {deposito} (50 %) zur Buchung; Restbetrag US$ {saldo} bis 30 Tage vor dem Trek.",
           "opcional": "Optional: {lista}.", "otra": "Weitere Option: {opcion}: US$ {precio} pro Person.",
           "alternativa": "Alternative", "tarjeta": "Karte", "paypal": "PayPal",
           "nivel": {"economico": "Economy", "estandar": "Standard", "premium": "Premium"}},
}

# Nombre y beneficio de los extras del demo (en, pt, fr, de). Un extra que la agencia agregue sin traducción
# sale con su nombre en español.
TEXTOS_EXTRA = {
    "bolsa_dormir": {
        "en": ("Sleeping bag rental", "stay warm on cold camp nights"),
        "pt": ("Aluguel de saco de dormir", "você dorme aquecido nas noites frias do acampamento"),
        "fr": ("Location de sac de couchage", "vous dormez au chaud pendant les nuits froides du campement"),
        "de": ("Schlafsack zur Miete", "warm schlafen in den kalten Nächten im Camp")},
    "bastones": {
        "en": ("Trekking poles rental", "less strain on your knees on the descents"),
        "pt": ("Aluguel de bastões", "menos carga nos joelhos nas descidas"),
        "fr": ("Location de bâtons", "moins d'effort pour les genoux dans les descentes"),
        "de": ("Wanderstöcke zur Miete", "weniger Belastung für die Knie beim Abstieg")},
    "huayna_picchu": {
        "en": ("Huayna Picchu entrance", "the best view of Machu Picchu from above"),
        "pt": ("Entrada em Huayna Picchu", "a melhor vista de Machu Picchu do alto"),
        "fr": ("Entrée au Huayna Picchu", "la plus belle vue sur le Machu Picchu d'en haut"),
        "de": ("Eintritt Huayna Picchu", "der beste Blick von oben auf Machu Picchu")},
    "caballo": {
        "en": ("Horse from Soraypampa to the Salkantay pass", "ride up the steepest stretch without wearing yourself out"),
        "pt": ("Cavalo de Soraypampa até o passo Salkantay", "você sobe o trecho mais íngreme sem se cansar"),
        "fr": ("Cheval de Soraypampa au col du Salkantay", "vous montez la partie la plus raide sans vous épuiser"),
        "de": ("Pferd von Soraypampa zum Salkantay-Pass", "der steilste Abschnitt ohne Erschöpfung")},
    "habitacion_individual": {
        "en": ("Single room", "your own room at the hotels on the trip"),
        "pt": ("Quarto individual", "seu próprio quarto nos hotéis da viagem"),
        "fr": ("Chambre individuelle", "votre propre chambre dans les hôtels du voyage"),
        "de": ("Einzelzimmer", "Ihr eigenes Zimmer in den Hotels der Reise")},
    "servicio_privado": {
        "en": ("Private service", "guide and departure just for your group"),
        "pt": ("Serviço privado", "guia e saída só para o seu grupo"),
        "fr": ("Service privé", "guide et départ rien que pour votre groupe"),
        "de": ("Privatservice", "Guide und Abfahrt nur für Ihre Gruppe")},
    "hotel_cusco_3": {
        "en": ("at a 3★ hotel in Cusco before the trek", "time to acclimatize to the altitude"),
        "pt": ("em hotel 3★ em Cusco antes do trekking", "tempo para se aclimatar à altitude"),
        "fr": ("dans un hôtel 3★ à Cusco avant le trek", "le temps de s'acclimater à l'altitude"),
        "de": ("im 3★-Hotel in Cusco vor dem Trek", "Zeit, sich an die Höhe zu gewöhnen")},
    "hotel_cusco_4": {
        "en": ("at a 4★ hotel in Cusco before the trek", "time to acclimatize to the altitude"),
        "pt": ("em hotel 4★ em Cusco antes do trekking", "tempo para se aclimatar à altitude"),
        "fr": ("dans un hôtel 4★ à Cusco avant le trek", "le temps de s'acclimater à l'altitude"),
        "de": ("im 4★-Hotel in Cusco vor dem Trek", "Zeit, sich an die Höhe zu gewöhnen")},
    "traslado_aeropuerto": {
        "en": ("Airport transfer to the hotel", "we pick you up at Cusco airport"),
        "pt": ("Traslado do aeroporto ao hotel", "esperamos você no aeroporto de Cusco"),
        "fr": ("Transfert de l'aéroport à l'hôtel", "nous vous attendons à l'aéroport de Cusco"),
        "de": ("Transfer vom Flughafen zum Hotel", "wir holen Sie am Flughafen Cusco ab")},
}
# El hotel en español sale del nombre de la fila ("Noche de hotel 3★ en Cusco"): en la línea va "1 noche en hotel…".
_HOTEL_ES = {"hotel_cusco_3": "en hotel 3★ en Cusco antes del trek", "hotel_cusco_4": "en hotel 4★ en Cusco antes del trek"}


def idioma_del_texto(idioma: str | None) -> str:
    codigo = (idioma or "").lower()
    return codigo if codigo in IDIOMAS else "en"


def monto(cents: int, idioma: str) -> str:
    """60000 -> '600'; 2750 -> '27.50' (en) o '27,50'. Sin separador de miles, como el resto de la cotización."""
    if cents % 100 == 0:
        return str(cents // 100)
    return f"{cents // 100}{'.' if idioma == 'en' else ','}{cents % 100:02d}"


def _nombre_y_beneficio(c: Componente, idioma: str, beneficios: dict[str, str]) -> tuple[str, str]:
    if idioma == "es":
        nombre = _HOTEL_ES.get(c.id, c.nombre)
        beneficio = c.beneficio
    else:
        nombre, beneficio = TEXTOS_EXTRA.get(c.id, {}).get(idioma, (c.nombre, c.beneficio))
    beneficio = beneficios.get(c.id) or beneficio  # el del modelo, escrito para este viajero
    if beneficio and idioma != "de":  # en alemán los sustantivos van con mayúscula
        beneficio = beneficio[:1].lower() + beneficio[1:]
    return nombre, beneficio or ""


def texto_paquete(paquete: Paquete, idioma: str, beneficios: dict[str, str] | None = None,
                  otras: list[OpcionCotizada] | None = None) -> str:
    """El bloque del paquete que va en el borrador: una línea por componente con su beneficio, totales,
    recargo, depósito y, en una sola línea, los extras no elegidos como opcionales."""
    from core.respuesta_nocturna import nombre_trek  # nombres de los treks traducidos

    idioma = idioma_del_texto(idioma)
    f = FRASES[idioma]
    beneficios = beneficios or {}
    p, o = paquete, paquete.opcion
    grupo = f["persona"] if p.personas == 1 else f["personas"].format(n=p.personas)
    ruta = o.trek_id.rsplit("_", 1)[0]
    trek = f["trek"].format(trek=nombre_trek(ruta, idioma), dias=o.dias, nivel=f["nivel"].get(o.nivel, o.nivel))
    if o.es_alternativa:
        trek += f" ({f['alternativa']})"
    lineas = [f["titulo"].format(grupo=grupo), f"• {trek}: US$ {o.precio_pp} {f['pp']}"]
    for c in p.modulo + p.extras:
        nombre, beneficio = _nombre_y_beneficio(c, idioma, beneficios)
        if c.id in HOTEL.values():
            nombre = f"{f['noches'].get(c.noches, str(c.noches))} {nombre}"
            precio = f"US$ {monto(c.precio_c * c.noches, idioma)} {f['pp']}"
        elif c.unidad == "por grupo":
            precio = f"US$ {monto(c.precio_c, idioma)} {f['grupo']}"
        elif c.unidad == "por noche":
            precio = f"US$ {monto(c.total_c // p.personas, idioma)} {f['pp']}"
        else:
            precio = f"US$ {monto(c.precio_c, idioma)} {f['pp']}"
        lineas.append(f"• {nombre}: {precio}" + (f" ({beneficio})" if beneficio else ""))
    lineas.append(f["total"].format(pp=monto(p.por_persona_c, idioma), total=monto(p.subtotal_c, idioma)))
    if p.recargo_c:
        lineas.append(f["recargo"].format(metodo=f.get(p.metodo_pago, p.metodo_pago), pct=f"{p.porcentaje_recargo:g}",
                                          recargo=monto(p.recargo_c, idioma), total=monto(p.total_c, idioma)))
    lineas.append(f["deposito"].format(deposito=monto(p.deposito_c, idioma), saldo=monto(p.saldo_c, idioma)))
    if p.opcionales:
        unidad = {"por persona": f["pp"], "por noche": f["noche"], "por grupo": f["grupo"]}
        lista = ", ".join(f"{_nombre_y_beneficio(c, idioma, {})[0]} US$ {monto(c.precio_c, idioma)} {unidad[c.unidad]}"
                          for c in p.opcionales)
        lineas.append(f["opcional"].format(lista=lista))
    for otra in otras or []:
        if otra is not o:
            nombre = f["trek"].format(trek=nombre_trek(otra.trek_id.rsplit("_", 1)[0], idioma), dias=otra.dias,
                                      nivel=f["nivel"].get(otra.nivel, otra.nivel))
            lineas.append(f["otra"].format(opcion=nombre, precio=otra.precio_pp))
    return "\n".join(lineas)
