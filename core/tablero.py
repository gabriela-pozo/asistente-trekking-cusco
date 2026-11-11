"""Datos del Tablero: consultas sintéticas del demo más las registradas en la app.

Las funciones de agregación no dependen de Streamlit, así se prueban solas
(tests/test_tablero.py).

Registro de consultas: el botón "Registrar como cotizada/reservada" guarda solo el perfil
agregado de la consulta (trek, idioma, mes del viaje, personas, nivel y monto). Nunca el
texto del mensaje ni el teléfono del viajero.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

from ai.fecha import MESES
from core.cotizacion import NOMBRE_RUTA

COLUMNAS = ["id", "fecha_consulta", "trek", "pais", "idioma", "mes_viaje", "personas", "nivel", "estado",
            "monto_usd"]
# Las registradas guardan además el día del último cambio de estado (core/mi_semana.py).
COLUMNAS_REGISTRO = COLUMNAS + ["fecha_estado"]
ESTADOS = ("cotizada", "reservada", "sin respuesta", "perdida")  # perdida: se marca en "Mi semana"
SIN_DATO = "no indicado"


def cargar_consultas(ruta_sinteticas: Path, ruta_registradas: Path | None = None) -> pd.DataFrame:
    """Sintéticas + registradas (si el archivo existe), con una columna 'origen'."""
    partes = [pd.read_csv(ruta_sinteticas).assign(origen="sintética")]
    if ruta_registradas is not None and Path(ruta_registradas).exists():
        registradas = pd.read_csv(ruta_registradas)
        if not registradas.empty:
            partes.append(registradas.assign(origen="registrada"))
    df = pd.concat(partes, ignore_index=True)
    df["mes_viaje"] = pd.to_numeric(df["mes_viaje"], errors="coerce").astype("Int64")
    df["monto_usd"] = pd.to_numeric(df["monto_usd"], errors="coerce").fillna(0)
    return df


def filtrar(df: pd.DataFrame, treks: list[str] | None = None, idiomas: list[str] | None = None) -> pd.DataFrame:
    """Sin selección no se filtra (una lista vacía = todos)."""
    if treks:
        df = df[df["trek"].isin(treks)]
    if idiomas:
        df = df[df["idioma"].isin(idiomas)]
    return df


def metricas(df: pd.DataFrame) -> dict:
    """Consultas, tasa de cierre, sin respuesta y monto reservado.

    Tasa de cierre = reservadas / consultas respondidas (cotizadas + reservadas): mide cuántas
    cotizaciones terminan en reserva. Las sin respuesta se cuentan aparte.
    """
    total = len(df)
    reservadas = int((df["estado"] == "reservada").sum())
    sin_respuesta = int((df["estado"] == "sin respuesta").sum())
    respondidas = total - sin_respuesta
    return {
        "consultas": total,
        "reservadas": reservadas,
        "respondidas": respondidas,
        "tasa_cierre": reservadas / respondidas if respondidas else 0.0,
        "sin_respuesta": sin_respuesta,
        "pct_sin_respuesta": sin_respuesta / total if total else 0.0,
        "monto_reservado": int(df.loc[df["estado"] == "reservada", "monto_usd"].sum()),
    }


def por_mes_viaje(df: pd.DataFrame) -> pd.DataFrame:
    """Consultas por mes del viaje, con los 12 meses aunque alguno tenga 0."""
    conteo = df["mes_viaje"].dropna().astype(int).value_counts()
    return pd.DataFrame({
        "mes": range(1, 13),
        "mes_nombre": [m[:3].capitalize() for m in MESES],
        "consultas": [int(conteo.get(m, 0)) for m in range(1, 13)],
    })


def por_trek(df: pd.DataFrame) -> pd.DataFrame:
    conteo = df["trek"].value_counts()
    return pd.DataFrame({"trek": [NOMBRE_RUTA.get(t, t) for t in conteo.index],
                         "consultas": conteo.values.astype(int)})


def por_pais(df: pd.DataFrame, maximo: int = 10) -> pd.DataFrame:
    conteo = df["pais"].fillna(SIN_DATO).value_counts().head(maximo)
    return pd.DataFrame({"pais": conteo.index, "consultas": conteo.values.astype(int)})


# --- Registro desde la app ------------------------------------------------------

def registro_desde_resultado(resultado, estado: str, hoy: date, numero: int) -> dict:
    """Fila agregada para el Tablero. Sin texto del mensaje ni teléfono."""
    if estado not in ESTADOS:
        raise ValueError(f"Estado '{estado}' no válido: {ESTADOS}")
    perfil = resultado.perfil
    opcion = resultado.opciones[0] if resultado.opciones else None
    trek = (perfil.treks_de_interes[0] if perfil.treks_de_interes
            else opcion.trek_id.rsplit("_", 1)[0] if opcion else SIN_DATO)
    return {
        "id": f"R{numero:03d}",
        "fecha_consulta": hoy.isoformat(),
        "trek": trek,
        "pais": SIN_DATO,  # el perfil no trae el país
        "idioma": perfil.idioma,
        "mes_viaje": perfil.mes_viaje if perfil.mes_viaje else "",
        "personas": perfil.num_personas or (opcion.personas if opcion else ""),
        "nivel": opcion.nivel if opcion else "",
        "estado": estado,
        "monto_usd": opcion.total if opcion and estado != "sin respuesta" else 0,
        "fecha_estado": hoy.isoformat(),
    }


def registrar(fila: dict, ruta: Path) -> int:
    """Agrega la fila al CSV de consultas registradas. Devuelve cuántas hay ahora."""
    ruta = Path(ruta)
    nuevo = pd.DataFrame([fila], columns=COLUMNAS_REGISTRO)
    if ruta.exists():
        anteriores = pd.read_csv(ruta)
        if "fecha_estado" not in anteriores:  # registros de antes de "Mi semana"
            anteriores["fecha_estado"] = anteriores["fecha_consulta"]
        df = pd.concat([anteriores, nuevo], ignore_index=True)
    else:
        ruta.parent.mkdir(parents=True, exist_ok=True)
        df = nuevo
    df.to_csv(ruta, index=False)
    return len(df)


def contar_registradas(ruta: Path) -> int:
    return len(pd.read_csv(ruta)) if Path(ruta).exists() else 0
