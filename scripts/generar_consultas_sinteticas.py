"""Genera data/consultas_sinteticas.csv: consultas INVENTADAS para el Tablero del demo.

Uso:  python scripts/generar_consultas_sinteticas.py

No son de ninguna agencia ni de ninguna persona real: no hay nombres, teléfonos ni textos,
solo el perfil agregado de cada consulta. La semilla es fija, así que el archivo sale
siempre igual (la prueba test_archivo_coincide_con_el_generador lo comprueba).

Supuestos de las distribuciones (plausibles, no medidos):
- Treks: Salkantay y Camino Inca reciben la mayoría de las consultas.
- Países: sobre todo Estados Unidos y Europa; el idioma sale del país.
- Mes del viaje: más en la temporada seca (mayo a septiembre). Ningún Camino Inca en febrero.
- Estado: 22 % reservada, 63 % cotizada, 15 % sin respuesta.
- Monto: precio del tarifario demo (data/tarifario_demo.csv) por el número de personas.
- Hora de llegada (hora de Lima) y día de la semana: el viajero escribe sobre todo en SU tarde-noche
  (19:00-23:00), y algo al mediodía y por la mañana, en su hora local. Se pasa a hora de Lima con la
  diferencia horaria de su país (HUSO, sin horario de verano). Por eso la noche de Lima recibe consultas:
  la mañana de Europa es la madrugada de Lima, y la noche de la costa oeste de EE. UU. es la medianoche de
  Lima. Se generan con otra semilla (SEMILLA_HORA), así no cambian las demás columnas.
"""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from core.cotizacion import cargar_tarifario, precio_por_persona  # noqa: E402

SEMILLA = 2026
SEMILLA_HORA = 2027  # aparte: agregar la hora no cambia las columnas que ya existían
N_CONSULTAS = 300
DESDE, HASTA = date(2025, 9, 1), date(2026, 10, 31)
SALIDA = RAIZ / "data" / "consultas_sinteticas.csv"

TREKS = {"salkantay": .34, "camino_inca": .24, "inca_jungle": .12, "choquequirao": .10,
         "camino_inca_corto": .11, "lares": .09}
PAISES = {  # país: (peso, idioma)
    "Estados Unidos": (.24, "en"), "Reino Unido": (.10, "en"), "Alemania": (.09, "de"), "Francia": (.08, "fr"),
    "España": (.08, "es"), "Brasil": (.08, "pt"), "Canadá": (.06, "en"), "Australia": (.06, "en"),
    "Perú": (.05, "es"), "Países Bajos": (.05, "en"), "Argentina": (.04, "es"), "México": (.04, "es"),
    "Israel": (.03, "en"),
}
PESO_MES = {1: .5, 2: .4, 3: .7, 4: 1.0, 5: 1.4, 6: 1.6, 7: 1.8, 8: 1.7, 9: 1.3, 10: 1.0, 11: .7, 12: .6}
PERSONAS = {1: .24, 2: .44, 3: .10, 4: .10, 5: .05, 6: .04, 8: .03}
NIVELES = {"economico": .30, "estandar": .50, "premium": .20}
ESTADOS = {"reservada": .22, "cotizada": .63, "sin respuesta": .15}
CERRADOS_EN_FEBRERO = {"camino_inca", "camino_inca_corto"}
LIMA_UTC = -5
HUSO = {  # país: {diferencia con UTC: peso} (hora estándar; EE. UU., Canadá y Brasil con varios husos)
    "Estados Unidos": {-5: .5, -6: .2, -8: .3}, "Canadá": {-5: .6, -8: .4}, "Reino Unido": {0: 1},
    "Alemania": {1: 1}, "Francia": {1: 1}, "España": {1: 1}, "Países Bajos": {1: 1}, "Brasil": {-3: 1},
    "Australia": {10: .6, 8: .4}, "Perú": {-5: 1}, "Argentina": {-3: 1}, "México": {-6: 1}, "Israel": {2: 1},
}
# Peso de cada hora LOCAL del viajero para escribir: poco de madrugada, algo de mañana y mediodía,
# lo más en la tarde-noche (después del trabajo).
PESO_HORA_LOCAL = {0: .3, 1: .15, 2: .1, 3: .05, 4: .05, 5: .1, 6: .3, 7: .6, 8: .9, 9: 1.0, 10: .9, 11: .8,
                   12: 1.0, 13: 1.0, 14: .8, 15: .7, 16: .7, 17: .8, 18: 1.0, 19: 1.4, 20: 1.7, 21: 1.8,
                   22: 1.4, 23: .8}
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


def _elegir(rng: np.random.Generator, pesos: dict):
    claves = list(pesos)
    p = np.array(list(pesos.values()), dtype=float)
    return claves[rng.choice(len(claves), p=p / p.sum())]


def generar(tarifario: pd.DataFrame, semilla: int = SEMILLA, n: int = N_CONSULTAS,
            semilla_hora: int = SEMILLA_HORA) -> pd.DataFrame:
    rng = np.random.default_rng(semilla)
    dias_rango = (HASTA - DESDE).days
    filas = []
    for i in range(1, n + 1):
        fecha = DESDE + timedelta(days=int(rng.integers(0, dias_rango + 1)))
        mes_viaje = int(_elegir(rng, PESO_MES))
        trek = _elegir(rng, TREKS)
        while mes_viaje == 2 and trek in CERRADOS_EN_FEBRERO:
            trek = _elegir(rng, TREKS)
        pais = _elegir(rng, {p: v[0] for p, v in PAISES.items()})
        personas = int(_elegir(rng, PERSONAS))
        nivel = _elegir(rng, NIVELES)
        estado = _elegir(rng, ESTADOS)
        opciones = tarifario[(tarifario["ruta"] == trek) & (tarifario["nivel"] == nivel)
                             & (tarifario["tamano_max_grupo"] >= personas)]
        if opciones.empty:  # premium admite hasta 8: con grupos grandes se cotiza estándar
            nivel = "estandar"
            opciones = tarifario[(tarifario["ruta"] == trek) & (tarifario["nivel"] == nivel)]
        fila_tarifa = opciones.iloc[int(rng.integers(0, len(opciones)))]
        monto = precio_por_persona(fila_tarifa, personas) * personas if estado != "sin respuesta" else 0
        filas.append({
            "id": f"S{i:03d}", "fecha_consulta": fecha.isoformat(), "trek": trek, "pais": pais,
            "idioma": PAISES[pais][1], "mes_viaje": mes_viaje, "personas": personas, "nivel": nivel,
            "estado": estado, "monto_usd": int(monto),
        })
    df = pd.DataFrame(filas).sort_values(["fecha_consulta", "id"]).reset_index(drop=True)
    df["id"] = [f"S{i:03d}" for i in range(1, len(df) + 1)]  # numeradas por fecha
    return agregar_llegada(df, semilla_hora)


def agregar_llegada(df: pd.DataFrame, semilla: int = SEMILLA_HORA) -> pd.DataFrame:
    """dia_semana (de fecha_consulta, que es el día en Lima) y hora_llegada (HH:MM, hora de Lima)."""
    rng = np.random.default_rng(semilla)
    horas = []
    for pais in df["pais"]:
        huso = _elegir(rng, HUSO[pais])
        local = _elegir(rng, PESO_HORA_LOCAL)
        horas.append(f"{(local + LIMA_UTC - huso) % 24:02d}:{int(rng.integers(0, 60)):02d}")
    df = df.copy()
    df["dia_semana"] = [DIAS[date.fromisoformat(f).weekday()] for f in df["fecha_consulta"]]
    df["hora_llegada"] = horas
    return df


if __name__ == "__main__":
    consultas = generar(cargar_tarifario(RAIZ / "data" / "tarifario_demo.csv"))
    consultas.to_csv(SALIDA, index=False)
    print(f"{len(consultas)} consultas sintéticas en {SALIDA.relative_to(RAIZ)}")
    print(consultas["estado"].value_counts().to_string())
