"""Sección "Mi semana": el avance del vendedor con SOLO sus consultas registradas en la app (nunca las sintéticas).

Compara al vendedor solo consigo mismo: esta semana contra la anterior y contra su mejor semana.
Semanas de lunes a domingo; las fechas son de Lima (las pone hoy_en_lima() al registrar).

- fecha_consulta: el día en que se registró la consulta (= el día en que se respondió).
- fecha_estado: el día del último cambio de estado (cotizada -> reservada o perdida). El monto reservado
  cuenta en la semana en que se reservó. Registros anteriores sin esta columna usan fecha_consulta.

Sin Streamlit: se prueba sola (tests/test_mi_semana.py).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

META_POR_DEFECTO = 20
DIAS_PARA_SEGUIMIENTO = 2  # una cotización espera seguimiento si lleva MÁS de 2 días sin reservarse
ESTADOS_DE_CIERRE = ("reservada", "perdida")


def inicio_semana(dia: date) -> date:
    return dia - timedelta(days=dia.weekday())


def leer_registradas(ruta: Path) -> pd.DataFrame:
    """Las consultas registradas, con fechas como date. Vacío si todavía no hay archivo."""
    ruta = Path(ruta)
    if not ruta.exists():
        return pd.DataFrame(columns=["id", "fecha_consulta", "fecha_estado", "trek", "personas", "estado",
                                     "monto_usd"])
    df = pd.read_csv(ruta)
    consulta = pd.to_datetime(df["fecha_consulta"])
    estado = pd.to_datetime(df["fecha_estado"]) if "fecha_estado" in df else pd.Series(pd.NaT, index=df.index)
    df["fecha_consulta"] = consulta.dt.date
    df["fecha_estado"] = estado.fillna(consulta).dt.date
    df["monto_usd"] = pd.to_numeric(df["monto_usd"], errors="coerce").fillna(0)
    return df


@dataclass
class Meta:
    respondidas: int
    meta: int

    @property
    def faltan(self) -> int:
        return max(self.meta - self.respondidas, 0)

    @property
    def cumplida(self) -> bool:
        return self.meta > 0 and self.respondidas >= self.meta

    @property
    def fraccion(self) -> float:
        return min(self.respondidas / self.meta, 1.0) if self.meta > 0 else 0.0


def progreso_meta(df: pd.DataFrame, hoy: date, meta: int = META_POR_DEFECTO) -> Meta:
    """Consultas respondidas (registradas) desde el lunes de esta semana hasta hoy."""
    lunes = inicio_semana(hoy)
    if df.empty:
        return Meta(0, meta)
    en_semana = (df["fecha_consulta"] >= lunes) & (df["fecha_consulta"] <= hoy)
    respondidas = int((en_semana & (df["estado"] != "sin respuesta")).sum())
    return Meta(respondidas, meta)


def reservado_por_semana(df: pd.DataFrame) -> dict[date, float]:
    """Monto reservado por semana (lunes), según el día en que se reservó."""
    reservadas = df[df["estado"] == "reservada"] if not df.empty else df
    salida: dict[date, float] = {}
    for dia, monto in zip(reservadas["fecha_estado"], reservadas["monto_usd"]):
        lunes = inicio_semana(dia)
        salida[lunes] = salida.get(lunes, 0) + float(monto)
    return salida


@dataclass
class Semana:
    esta: float
    anterior: float
    mejor_anterior: float  # la mejor semana antes de esta (0 si no hubo reservas antes)

    @property
    def variacion(self) -> float:
        return self.esta - self.anterior

    @property
    def supera_mejor(self) -> bool:
        """Hito: esta semana ya reservó más que su mejor semana anterior (si hubo una)."""
        return self.mejor_anterior > 0 and self.esta > self.mejor_anterior


def semana(df: pd.DataFrame, hoy: date) -> Semana:
    por_semana = reservado_por_semana(df)
    lunes = inicio_semana(hoy)
    anteriores = [m for s, m in por_semana.items() if s < lunes]
    return Semana(esta=por_semana.get(lunes, 0.0), anterior=por_semana.get(lunes - timedelta(days=7), 0.0),
                  mejor_anterior=max(anteriores, default=0.0))


@dataclass
class Racha:
    dias: int
    registro_hoy: bool


def racha(df: pd.DataFrame, hoy: date) -> Racha:
    """Días seguidos con al menos una consulta registrada, hasta hoy.

    Si hoy todavía no registró nada, la racha que terminó ayer sigue viva (el día no ha terminado).
    Un día sin registros la corta.
    """
    dias = set(df["fecha_consulta"]) if not df.empty else set()
    registro_hoy = hoy in dias
    dia = hoy if registro_hoy else hoy - timedelta(days=1)
    cuenta = 0
    while dia in dias:
        cuenta += 1
        dia -= timedelta(days=1)
    return Racha(cuenta, registro_hoy)


def pendientes(df: pd.DataFrame, hoy: date, dias: int = DIAS_PARA_SEGUIMIENTO) -> pd.DataFrame:
    """Cotizadas hace más de `dias` días que no pasaron a reservada ni a perdida. Las más antiguas primero."""
    if df.empty:
        return df
    limite = hoy - timedelta(days=dias)
    esperan = df[(df["estado"] == "cotizada") & (df["fecha_estado"] < limite)]
    return esperan.sort_values("fecha_estado")


def cambiar_estado(ruta: Path, id_consulta: str, estado: str, hoy: date) -> None:
    """Marca una consulta registrada como reservada o perdida (y anota el día del cambio)."""
    if estado not in ESTADOS_DE_CIERRE:
        raise ValueError(f"Estado '{estado}' no válido: {ESTADOS_DE_CIERRE}")
    ruta = Path(ruta)
    df = pd.read_csv(ruta)
    fila = df["id"] == id_consulta
    if not fila.any():
        raise KeyError(id_consulta)
    if "fecha_estado" not in df:
        df["fecha_estado"] = df["fecha_consulta"]
    df.loc[fila, ["estado", "fecha_estado"]] = [estado, hoy.isoformat()]
    df.to_csv(ruta, index=False)
