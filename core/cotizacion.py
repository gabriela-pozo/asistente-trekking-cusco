"""Cotización a partir del tarifario de la agencia.

Los precios los calcula este código, nunca el modelo de lenguaje: el modelo solo
redacta el mensaje con las cifras que este módulo le entrega.

El perfil del turista puede ser cualquier objeto con estos atributos (los que
falten se toman como "sin dato"):
    num_personas: int | None
    mes_viaje: int | None            (1 a 12)
    dias_disponibles: int | None
    treks_de_interes: list[str]      ("salkantay", "camino_inca")
    nivel_preferido: str | None      ("economico", "estandar", "premium")
    presupuesto_usd_pp: int | None
    extras_de_interes: list[str]     ("huayna_picchu", "vistadome")
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

NOMBRE_NIVEL = {"economico": "económico", "estandar": "estándar", "premium": "premium"}
ORDEN_NIVEL = {"estandar": 0, "economico": 1, "premium": 2}
PERSONAS_POR_DEFECTO = 2


@dataclass
class OpcionCotizada:
    trek_id: str
    trek: str
    dias: int
    nivel: str
    precio_pp: int                      # solo el trek, por persona
    personas: int
    extras: list[tuple[str, int]] = field(default_factory=list)  # (nombre, precio por persona)
    requiere_permiso: bool = False
    es_alternativa: bool = False        # True si se ofrece porque lo pedido no estaba disponible
    incluye: list[str] = field(default_factory=list)
    no_incluye: list[str] = field(default_factory=list)

    @property
    def precio_pp_con_extras(self) -> int:
        return self.precio_pp + sum(p for _, p in self.extras)

    @property
    def total(self) -> int:
        return self.precio_pp_con_extras * self.personas

    def resumen(self) -> str:
        texto = (
            f"{self.trek}, {self.dias} días, nivel {NOMBRE_NIVEL.get(self.nivel, self.nivel)}: "
            f"US$ {self.precio_pp} por persona (grupo de {self.personas})"
        )
        for nombre, precio in self.extras:
            texto += f" + {nombre} US$ {precio} por persona"
        texto += (
            f". Total US$ {self.total}. Incluye: {', '.join(self.incluye)}. "
            f"No incluye: {', '.join(self.no_incluye)}."
        )
        if self.requiere_permiso:
            texto += " Requiere permiso del Camino Inca: verificar disponibilidad antes de confirmar."
        if self.es_alternativa:
            texto += " Se ofrece como alternativa porque lo pedido no está disponible."
        return texto


def cargar_tarifario(ruta) -> pd.DataFrame:
    df = pd.read_csv(ruta, dtype={"meses_no_disponible": str})
    df["meses_no_disponible"] = df["meses_no_disponible"].fillna("")
    return df


def cargar_extras(ruta) -> pd.DataFrame:
    return pd.read_csv(ruta)


def precio_por_persona(fila: pd.Series, personas: int) -> int:
    """Precio por persona según el tamaño del grupo (1 o 2 personas pagan la tarifa base)."""
    if personas <= 2:
        return int(fila["precio_usd_pp_grupo_2"])
    if personas <= 4:
        return int(fila["precio_usd_pp_grupo_3a4"])
    return int(fila["precio_usd_pp_grupo_5mas"])


def disponible_en_mes(fila: pd.Series, mes: int | None) -> bool:
    if mes is None or not fila["meses_no_disponible"]:
        return True
    cerrados = {int(m) for m in str(fila["meses_no_disponible"]).replace(";", ",").split(",") if m.strip()}
    return mes not in cerrados


def _extras_para(nivel: str, pedidos: list[str], extras: pd.DataFrame | None) -> list[tuple[str, int]]:
    if extras is None or not pedidos:
        return []
    elegidos = []
    for _, e in extras.iterrows():
        if e["extra_id"] in pedidos and nivel in str(e["aplica_a_niveles"]).split(";"):
            elegidos.append((e["extra"], int(e["precio_usd_pp"])))
    return elegidos


def opciones_para_perfil(perfil, tarifario: pd.DataFrame, extras: pd.DataFrame | None = None,
                         maximo: int = 3) -> list[OpcionCotizada]:
    """Elige hasta `maximo` opciones del tarifario que encajan con el perfil."""
    personas = getattr(perfil, "num_personas", None) or PERSONAS_POR_DEFECTO
    mes = getattr(perfil, "mes_viaje", None)
    dias = getattr(perfil, "dias_disponibles", None)
    interes = [t for t in (getattr(perfil, "treks_de_interes", None) or []) if t in set(tarifario["ruta"])]
    nivel_preferido = getattr(perfil, "nivel_preferido", None)
    presupuesto = getattr(perfil, "presupuesto_usd_pp", None)
    extras_pedidos = getattr(perfil, "extras_de_interes", None) or []

    cabe = tarifario["tamano_max_grupo"] >= personas
    df = tarifario[cabe]
    if interes:
        df = df[df["ruta"].isin(interes)]
    df = df[df.apply(lambda f: disponible_en_mes(f, mes), axis=1)]
    if dias:
        df = df[df["dias"] <= dias]

    # Si lo pedido no está disponible (p. ej. Camino Inca en febrero), ofrecer Salkantay,
    # que no requiere permiso y se opera todo el año.
    es_alternativa = False
    if df.empty:
        es_alternativa = True
        df = tarifario[cabe & (tarifario["ruta"] == "salkantay")]
        df = df[df.apply(lambda f: disponible_en_mes(f, mes), axis=1)]
    if df.empty:
        return []

    df = df.assign(precio_pp=df.apply(lambda f: precio_por_persona(f, personas), axis=1))
    if nivel_preferido:
        prioridad = (df["nivel"] != nivel_preferido).astype(int)
    elif presupuesto:
        prioridad = (df["precio_pp"] - presupuesto).abs()
    else:
        prioridad = df["nivel"].map(ORDEN_NIVEL)
    df = df.assign(_prioridad=prioridad).sort_values(["_prioridad", "precio_pp"]).head(maximo)

    return [
        OpcionCotizada(
            trek_id=f["trek_id"],
            trek=f["trek"],
            dias=int(f["dias"]),
            nivel=f["nivel"],
            precio_pp=int(f["precio_pp"]),
            personas=personas,
            extras=_extras_para(f["nivel"], extras_pedidos, extras),
            requiere_permiso=f["requiere_permiso_camino_inca"] == "si",
            es_alternativa=es_alternativa,
            incluye=[x.strip() for x in str(f["incluye"]).split(";")],
            no_incluye=[x.strip() for x in str(f["no_incluye"]).split(";")],
        )
        for _, f in df.iterrows()
    ]
