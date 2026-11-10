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


def _elegir(rng: np.random.Generator, pesos: dict):
    claves = list(pesos)
    p = np.array(list(pesos.values()), dtype=float)
    return claves[rng.choice(len(claves), p=p / p.sum())]


def generar(tarifario: pd.DataFrame, semilla: int = SEMILLA, n: int = N_CONSULTAS) -> pd.DataFrame:
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
    return df


if __name__ == "__main__":
    consultas = generar(cargar_tarifario(RAIZ / "data" / "tarifario_demo.csv"))
    consultas.to_csv(SALIDA, index=False)
    print(f"{len(consultas)} consultas sintéticas en {SALIDA.relative_to(RAIZ)}")
    print(consultas["estado"].value_counts().to_string())
