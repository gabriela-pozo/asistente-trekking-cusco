"""Resumen de precios del mercado por trek (mínimo, mediana y máximo).

Uso:  python scripts/analisis_precios.py
Lee data/precios_mercado.csv y usa solo las filas con incluir_en_analisis = "si".
"""
from pathlib import Path

import pandas as pd

RUTA = Path(__file__).resolve().parent.parent / "data" / "precios_mercado.csv"


def resumen(df: pd.DataFrame) -> pd.DataFrame:
    """Devuelve una fila por trek con n, mínimo, mediana y máximo en USD por persona."""
    validos = df[df["incluir_en_analisis"] == "si"]
    return (
        validos.groupby(["trek", "dias"])["precio_usd_pp"]
        .agg(n="count", minimo="min", mediana="median", maximo="max")
        .reset_index()
    )


if __name__ == "__main__":
    datos = pd.read_csv(RUTA)
    print(f"Publicaciones registradas: {len(datos)} "
          f"(excluidas del análisis: {(datos['incluir_en_analisis'] == 'no').sum()})\n")
    print(resumen(datos).to_string(index=False))

    print("\nSin la opción premium (solo servicio de grupo estándar):")
    sin_premium = datos[datos["nivel_aprox"] != "premium"]
    print(resumen(sin_premium).to_string(index=False))

    print("\nBolsa de dormir incluida:")
    print(datos["incluye_bolsa_dormir"].value_counts().to_string())
