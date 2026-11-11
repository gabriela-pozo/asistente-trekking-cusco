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


# --- Tablero por preguntas: período, variación, horario, cierre, estado, países y embudo -------------

COLUMNAS_SINTETICAS = COLUMNAS + ["dia_semana", "hora_llegada"]
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
ORDEN_ESTADOS = ["reservada", "cotizada", "sin respuesta", "perdida"]
PERIODOS = {"Últimos 3 meses": 3, "Últimos 6 meses": 6, "Últimos 12 meses": 12}
APERTURA_H, CIERRE_H = 8, 20  # horario de atención en hora de Lima (como core/respuesta_nocturna.py)


def periodo(df: pd.DataFrame, meses: int) -> tuple[pd.DataFrame, pd.DataFrame, bool, tuple]:
    """(actual, anterior, anterior_completo, (desde, hasta)).

    El período actual son los últimos `meses` meses hasta la consulta más reciente; el anterior, los
    `meses` meses justo antes. anterior_completo es False si los datos no cubren todo el período anterior:
    entonces no se muestra la variación (compararía contra un período más corto).
    """
    fechas = pd.to_datetime(df["fecha_consulta"])
    if fechas.empty:
        return df, df, False, (None, None)
    hasta = fechas.max().normalize()
    desde = hasta - pd.DateOffset(months=meses) + pd.Timedelta(days=1)
    desde_anterior = desde - pd.DateOffset(months=meses)
    actual = df[(fechas >= desde) & (fechas <= hasta)]
    anterior = df[(fechas >= desde_anterior) & (fechas < desde)]
    return actual, anterior, bool(fechas.min() <= desde_anterior), (desde.date(), hasta.date())


def variaciones(actual: pd.DataFrame, anterior: pd.DataFrame) -> dict:
    """Cambio de cada indicador frente al período anterior (absoluto; la tasa en puntos porcentuales)."""
    a, b = metricas(actual), metricas(anterior)
    return {
        "consultas": a["consultas"] - b["consultas"],
        "pct_consultas": (a["consultas"] - b["consultas"]) / b["consultas"] if b["consultas"] else None,
        "tasa_cierre_pp": (a["tasa_cierre"] - b["tasa_cierre"]) * 100,
        "sin_respuesta": a["sin_respuesta"] - b["sin_respuesta"],
        "monto_reservado": a["monto_reservado"] - b["monto_reservado"],
    }


def _hora(df: pd.DataFrame) -> pd.Series:
    if "hora_llegada" not in df:
        return pd.Series(dtype="int64")
    horas = pd.to_numeric(df["hora_llegada"].astype("string").str.slice(0, 2), errors="coerce")
    return horas.dropna().astype(int)


def fuera_de_horario(df: pd.DataFrame, apertura: int = APERTURA_H, cierre: int = CIERRE_H) -> tuple[float, int]:
    """(% de consultas que llegan antes de la apertura o desde el cierre, cuántas tienen hora)."""
    horas = _hora(df)
    if horas.empty:
        return 0.0, 0
    return float(((horas < apertura) | (horas >= cierre)).mean()), len(horas)


def por_dia_y_hora(df: pd.DataFrame) -> pd.DataFrame:
    """Las 7 × 24 celdas (con 0 donde no hay consultas). Solo las consultas que tienen hora de llegada."""
    horas = _hora(df)
    dias = df.loc[horas.index, "dia_semana"] if "dia_semana" in df else pd.Series(index=horas.index, dtype="object")
    conteo = pd.DataFrame({"dia": dias, "hora": horas}).value_counts()
    filas = [{"dia": d, "dia_n": i, "hora": h, "hora_fin": h + 1, "consultas": int(conteo.get((d, h), 0)),
              "franja": f"{h:02d}:00–{h:02d}:59"} for i, d in enumerate(DIAS) for h in range(24)]
    return pd.DataFrame(filas)


def cierre_por_trek(df: pd.DataFrame) -> pd.DataFrame:
    """Por trek: consultas, respondidas, reservadas y tasa de cierre (reservadas / respondidas). Más pedido primero."""
    columnas = ["nombre", "trek", "consultas", "respondidas", "reservadas", "tasa_cierre"]
    if df.empty:
        return pd.DataFrame(columns=columnas)
    g = df.assign(_resp=df["estado"] != "sin respuesta", _res=df["estado"] == "reservada").groupby("trek")
    t = pd.DataFrame({"consultas": g.size(), "respondidas": g["_resp"].sum(), "reservadas": g["_res"].sum()})
    t["tasa_cierre"] = (t["reservadas"] / t["respondidas"].where(t["respondidas"] > 0)).fillna(0.0)
    t = t.reset_index().sort_values(["consultas", "trek"], ascending=[False, True])
    t.insert(0, "nombre", [NOMBRE_RUTA.get(x, x) for x in t["trek"]])
    return t.astype({"consultas": int, "respondidas": int, "reservadas": int}).reset_index(drop=True)[columnas]


def por_mes_y_estado(df: pd.DataFrame) -> pd.DataFrame:
    """Mes del viaje × estado (los 12 meses; solo los estados que aparecen)."""
    estados = [e for e in ORDEN_ESTADOS if e in set(df["estado"])]
    datos = df.dropna(subset=["mes_viaje"])
    conteo = datos.groupby([datos["mes_viaje"].astype(int), "estado"]).size()
    filas = [{"mes": m, "mes_nombre": MESES[m - 1][:3].capitalize(), "estado": e, "orden": ORDEN_ESTADOS.index(e),
              "consultas": int(conteo.get((m, e), 0))} for m in range(1, 13) for e in estados]
    return pd.DataFrame(filas, columns=["mes", "mes_nombre", "estado", "orden", "consultas"])


def paises_con_otros(df: pd.DataFrame, top: int = 7) -> pd.DataFrame:
    """Los `top` países con más consultas y el resto sumado en "Otros" (siempre al final)."""
    conteo = df["pais"].fillna(SIN_DATO).value_counts()
    conteo = conteo.sort_index().sort_values(ascending=False, kind="stable")  # empates: por nombre
    salida = pd.DataFrame({"pais": list(conteo.index[:top]), "consultas": conteo.values[:top].astype(int)})
    resto = int(conteo.iloc[top:].sum())
    if resto:
        salida = pd.concat([salida, pd.DataFrame({"pais": ["Otros"], "consultas": [resto]})], ignore_index=True)
    total = int(conteo.sum())
    salida["porcentaje"] = salida["consultas"] / total if total else 0.0
    return salida


def embudo(df: pd.DataFrame) -> pd.DataFrame:
    """Consultas → respondidas → cotizadas (respondidas con precio) → reservadas, con % de la etapa anterior."""
    respondidas = df["estado"] != "sin respuesta"
    cotizadas = respondidas & (pd.to_numeric(df["monto_usd"], errors="coerce").fillna(0) > 0)
    numeros = [len(df), int(respondidas.sum()), int(cotizadas.sum()), int((df["estado"] == "reservada").sum())]
    anteriores = [None] + numeros[:-1]
    return pd.DataFrame({
        "etapa": ["Consultas", "Respondidas", "Cotizadas", "Reservadas"], "orden": range(4), "numero": numeros,
        "pct_anterior": [None if a is None else (n / a if a else 0.0) for n, a in zip(numeros, anteriores)],
    })


# --- Hallazgos: una frase por gráfico, calculada con los datos filtrados ----------------------------

def pct(valor: float) -> str:
    return f"{round(valor * 100)} %"


def hallazgo_horario(df: pd.DataFrame) -> str:
    fuera, n = fuera_de_horario(df)
    if not n:
        return "Estas consultas no tienen hora de llegada."
    pico = int(_hora(df).value_counts().sort_index().idxmax())
    return (f"El {pct(fuera)} de las consultas llega fuera de horario (antes de las {APERTURA_H}:00 o desde las "
            f"{CIERRE_H}:00). La hora con más consultas: de {pico}:00 a {pico}:59.")


def hallazgo_treks(t: pd.DataFrame) -> str:
    if t.empty:
        return ""
    primero = t.iloc[0]
    texto = f"{primero['nombre']} concentra el {pct(primero['consultas'] / t['consultas'].sum())} de las consultas."
    con_base = t[t["respondidas"] >= 10]  # con menos de 10 respondidas la tasa de cierre dice poco
    if len(con_base) > 1:
        mejor = con_base.sort_values(["tasa_cierre", "consultas"], ascending=False).iloc[0]
        texto += f" Mejor cierre: {mejor['nombre']} ({pct(mejor['tasa_cierre'])})."
    return texto


def hallazgo_meses(m: pd.DataFrame) -> str:
    por_mes = m.groupby("mes")["consultas"].sum()
    if por_mes.sum() == 0:
        return ""
    top = int(por_mes.idxmax())  # el primero si empatan
    total = int(por_mes[top])
    reservadas = int(m[(m["mes"] == top) & (m["estado"] == "reservada")]["consultas"].sum())
    return (f"{MESES[top - 1].capitalize()} es el mes de viaje más pedido ({total} consultas); "
            f"el {pct(reservadas / total)} ya está reservado.")


def hallazgo_paises(p: pd.DataFrame) -> str:
    tres = p[p["pais"] != "Otros"].head(3)
    if tres.empty:
        return ""
    if len(tres) == 1:
        return f"{tres['pais'].iloc[0]} es el {pct(tres['porcentaje'].iloc[0])} de las consultas."
    nombres = ", ".join(tres["pais"].iloc[:-1]) + f" y {tres['pais'].iloc[-1]}"
    return f"{nombres} suman el {pct(tres['porcentaje'].sum())} de las consultas."


def hallazgo_embudo(e: pd.DataFrame) -> str:
    if e["numero"].iloc[0] == 0:
        return ""
    etapas = e.iloc[1:]
    peor = etapas.loc[etapas["pct_anterior"].astype(float).idxmin()]
    anterior = e.iloc[int(peor["orden"]) - 1]["etapa"].lower()
    por_cien = round(e["numero"].iloc[-1] / e["numero"].iloc[0] * 100)
    return (f"La mayor caída es de {anterior} a {peor['etapa'].lower()}: pasa el {pct(peor['pct_anterior'])}. "
            f"De cada 100 consultas, {por_cien} terminan en reserva.")
