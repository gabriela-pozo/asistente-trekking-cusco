"""Análisis de precios del mercado y generación del tarifario de la agencia demo.

Uso:  python scripts/analisis_precios.py

1. Lee data/precios_mercado.csv y muestra mínimo, mediana y máximo por trek.
2. Lee data/precios_otros_treks.csv (Choquequirao, Lares, Inca Jungle, Camino Inca corto).
3. Genera data/tarifario_demo.csv para "Andes Trek Demo" con las reglas de abajo.
4. Lee data/extras_mercado.csv y genera data/extras_demo.csv.

En precios_mercado.csv solo se usan las filas con incluir_en_analisis = "si".
precios_otros_treks.csv no tiene esa columna ni el nivel: se usan todas sus filas.
Un trek con menos de MIN_PRECIOS_TREK precios no entra al tarifario.
Las reglas están explicadas en docs/fuentes_precios.md.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
DATA = RAIZ / "data"

# --- Reglas de precios (supuestos de la agencia demo) -----------------------
DESCUENTO_ECONOMICO = 0.20   # económico = estándar - 20 %
RECARGO_PREMIUM = 0.60       # premium = estándar + 60 %
DESCUENTO_GRUPO_3A4 = 0.04   # 3 a 4 personas
DESCUENTO_GRUPO_5MAS = 0.08  # 5 o más personas
FACTOR_SALKANTAY_4D = 0.90   # si el 4 días sale más caro que el 5 días: 5 días - 10 %
MIN_PRECIOS_PREMIUM = 3      # con al menos 3 precios premium reales, premium = su mediana (no el +60 %)
MIN_PRECIOS_TREK = 3         # un trek con menos de 3 precios del mercado no entra al tarifario

ARCHIVO_MERCADO = "precios_mercado.csv"
ARCHIVO_OTROS = "precios_otros_treks.csv"

# Origen de cada precio del tarifario (columna origen_precio)
ORIGEN_MERCADO = "mediana del mercado"
ORIGEN_SUPUESTO = "supuesto"

# Treks del tarifario: clave = (trek, dias) tal como aparecen en precios_mercado.csv
TREKS = {
    ("Salkantay", 4): {
        "trek_id": "salkantay_4d", "ruta": "salkantay", "nombre": "Salkantay a Machu Picchu",
        "requiere_permiso_camino_inca": "no", "meses_no_disponible": "", "estilo": "campamento",
    },
    ("Salkantay", 5): {
        "trek_id": "salkantay_5d", "ruta": "salkantay", "nombre": "Salkantay a Machu Picchu",
        "requiere_permiso_camino_inca": "no", "meses_no_disponible": "", "estilo": "campamento",
    },
    ("Camino Inca clásico", 4): {
        "trek_id": "camino_inca_4d", "ruta": "camino_inca", "nombre": "Camino Inca clásico",
        "requiere_permiso_camino_inca": "si", "meses_no_disponible": "2",  # cerrado en febrero
        "estilo": "campamento",
    },
}

# Treks de data/precios_otros_treks.csv. Permisos, cierres y estilo según data/knowledge/<ruta>.md.
OTROS_TREKS = {
    ("Choquequirao trek", 4): {
        "trek_id": "choquequirao_4d", "ruta": "choquequirao", "nombre": "Choquequirao (ida y vuelta)",
        "requiere_permiso_camino_inca": "no", "meses_no_disponible": "",
        "estilo": "campamento_sin_machu_picchu",  # ida y vuelta desde Capuliyoc: no llega a Machu Picchu
    },
    ("Lares trek", 4): {
        "trek_id": "lares_4d", "ruta": "lares", "nombre": "Lares a Machu Picchu",
        "requiere_permiso_camino_inca": "no", "meses_no_disponible": "", "estilo": "campamento",
    },
    ("Inca Jungle trek", 4): {
        "trek_id": "inca_jungle_4d", "ruta": "inca_jungle", "nombre": "Inca Jungle a Machu Picchu",
        "requiere_permiso_camino_inca": "no", "meses_no_disponible": "", "estilo": "hospedaje",  # sin campamento
    },
    ("Camino Inca corto (KM 104)", 2): {
        "trek_id": "camino_inca_corto_2d", "ruta": "camino_inca_corto", "nombre": "Camino Inca corto (KM 104)",
        "requiere_permiso_camino_inca": "si", "meses_no_disponible": "2",  # todas las rutas del Camino Inca cierran en febrero
        "estilo": "hospedaje",  # se duerme en Aguas Calientes
    },
}

INCLUYE_BASE = {
    "salkantay": "Guía bilingüe; transporte de ida; comidas durante el trek; entrada a Machu Picchu; "
                 "tren de regreso a Ollantaytambo",
    "camino_inca": "Permiso del Camino Inca; guía bilingüe; porteadores; comidas durante el trek; "
                   "entrada a Machu Picchu; tren de regreso a Ollantaytambo",
    "choquequirao": "Guía bilingüe; transporte ida y vuelta desde Cusco; comidas durante el trek; "
                    "entrada al sitio arqueológico de Choquequirao",
    "lares": "Guía bilingüe; transporte de ida; comidas durante el trek; 1 noche en Aguas Calientes; "
             "entrada a Machu Picchu; tren de regreso a Ollantaytambo",
    "inca_jungle": "Guía bilingüe; transporte de ida; bicicleta y casco para la bajada; comidas durante el trek; "
                   "entrada a Machu Picchu; tren de regreso a Ollantaytambo",
    "camino_inca_corto": "Permiso del Camino Inca; guía bilingüe; tren al KM 104; almuerzo del día de caminata; "
                         "entrada a Machu Picchu; tren de regreso a Ollantaytambo",
}

NIVELES = {
    "economico": {
        "tamano_max_grupo": 16,
        "incluye": "campamentos básicos",
        "no_incluye": "Bolsa de dormir (alquiler aparte); seguro de viaje; propinas; Huayna Picchu",
    },
    "estandar": {
        "tamano_max_grupo": 12,
        "incluye": "carpa doble y colchoneta",
        "no_incluye": "Bolsa de dormir (alquiler aparte); seguro de viaje; propinas; Huayna Picchu",
    },
    "premium": {
        "tamano_max_grupo": 8,
        "incluye": "domos o carpas premium; bolsa de dormir; tren Vistadome de regreso",
        "no_incluye": "Seguro de viaje; propinas; Huayna Picchu",
    },
}

# Qué agrega cada nivel según el estilo del trek (supuesto, como NIVELES).
NIVELES_POR_ESTILO = {
    "campamento": NIVELES,
    "campamento_sin_machu_picchu": {
        "economico": {**NIVELES["economico"], "no_incluye": "Bolsa de dormir (alquiler aparte); seguro de viaje; propinas"},
        "estandar": {**NIVELES["estandar"], "no_incluye": "Bolsa de dormir (alquiler aparte); seguro de viaje; propinas"},
        "premium": {**NIVELES["premium"], "incluye": "domos o carpas premium; bolsa de dormir",
                    "no_incluye": "Seguro de viaje; propinas"},
    },
    "hospedaje": {
        "economico": {**NIVELES["economico"], "incluye": "hostal sencillo",
                      "no_incluye": "Seguro de viaje; propinas; Huayna Picchu"},
        "estandar": {**NIVELES["estandar"], "incluye": "hotel turista en habitación doble",
                     "no_incluye": "Seguro de viaje; propinas; Huayna Picchu"},
        "premium": {**NIVELES["premium"], "incluye": "hotel 3 estrellas; tren Vistadome de regreso"},
    },
}


def redondear(valor: float, paso: int = 10) -> int:
    """Redondea al múltiplo de `paso` más cercano (las mitades hacia arriba)."""
    return int(valor / paso + 0.5) * paso


def validos(df: pd.DataFrame) -> pd.DataFrame:
    return df[df["incluir_en_analisis"] == "si"]


def resumen(df: pd.DataFrame) -> pd.DataFrame:
    """Una fila por trek con n, mínimo, mediana y máximo en USD por persona."""
    return (
        validos(df).groupby(["trek", "dias"])["precio_usd_pp"]
        .agg(n="count", minimo="min", mediana="median", maximo="max")
        .reset_index()
    )


def precios_estandar(mercado: pd.DataFrame) -> tuple[dict, list[str]]:
    """Precio estándar por trek y la lista de reglas que se aplicaron.

    Cada valor es (precio, origen): "mediana del mercado", o "supuesto" si se aplicó la regla del 4 días.
    """
    base = validos(mercado)
    base = base[base["nivel_aprox"] != "premium"]
    medianas = base.groupby(["trek", "dias"])["precio_usd_pp"].median().to_dict()

    estandar, notas = {}, []
    for clave in TREKS:
        estandar[clave] = (redondear(medianas[clave]), ORIGEN_MERCADO)
        notas.append(f"{clave[0]} {clave[1]} días: mediana {medianas[clave]:g} -> estándar {estandar[clave][0]}")

    s4, s5 = ("Salkantay", 4), ("Salkantay", 5)
    if medianas[s4] > medianas[s5]:
        estandar[s4] = (redondear(estandar[s5][0] * FACTOR_SALKANTAY_4D), ORIGEN_SUPUESTO)
        notas.append(
            f"Salkantay 4 días: su mediana ({medianas[s4]:g}) supera a la de 5 días ({medianas[s5]:g}); "
            f"se usa el estándar de 5 días menos 10 % -> {estandar[s4][0]}"
        )
    return estandar, notas


def precios_premium(mercado: pd.DataFrame, estandar: dict) -> tuple[dict, list[str]]:
    """Premium por trek: mediana de los precios premium reales si hay al menos
    MIN_PRECIOS_PREMIUM; si no, estándar + RECARGO_PREMIUM (supuesto)."""
    base = validos(mercado)
    base = base[base["nivel_aprox"] == "premium"]
    premium, notas = {}, []
    for clave in TREKS:
        precios = base[(base["trek"] == clave[0]) & (base["dias"] == clave[1])]["precio_usd_pp"]
        if len(precios) >= MIN_PRECIOS_PREMIUM:
            premium[clave] = (redondear(precios.median()), ORIGEN_MERCADO)
            notas.append(f"{clave[0]} {clave[1]} días: {len(precios)} precios premium, mediana "
                         f"{precios.median():g} -> premium {premium[clave][0]}")
        else:
            premium[clave] = (redondear(estandar[clave][0] * (1 + RECARGO_PREMIUM)), ORIGEN_SUPUESTO)
            notas.append(f"{clave[0]} {clave[1]} días: {len(precios)} precio(s) premium (menos de "
                         f"{MIN_PRECIOS_PREMIUM}) -> estándar + 60 % = {premium[clave][0]}")
    return premium, notas


def precios_otros(otros: pd.DataFrame) -> tuple[dict, list[str], list[str]]:
    """Estándar de los treks de precios_otros_treks.csv = mediana de todos sus precios.

    Devuelve (estándar por trek como (precio, n), notas, treks que quedaron fuera por tener
    menos de MIN_PRECIOS_TREK precios).
    """
    estandar, notas, fuera = {}, [], []
    for clave in OTROS_TREKS:
        precios = otros[(otros["trek"] == clave[0]) & (otros["dias"] == clave[1])]["precio_usd_pp"]
        if len(precios) < MIN_PRECIOS_TREK:
            fuera.append(f"{clave[0]} {clave[1]} días: {len(precios)} precio(s), menos de {MIN_PRECIOS_TREK}")
            continue
        estandar[clave] = (redondear(precios.median()), len(precios))
        notas.append(f"{clave[0]} {clave[1]} días: {len(precios)} precios, mediana {precios.median():g} "
                     f"-> estándar {estandar[clave][0]}")
    return estandar, notas, fuera


def _n_precios(mercado: pd.DataFrame, premium: bool) -> dict:
    base = validos(mercado)
    base = base[(base["nivel_aprox"] == "premium") == premium]
    return base.groupby(["trek", "dias"])["precio_usd_pp"].count().to_dict()


def _origen_mediana(n: int, archivo: str, premium: bool = False) -> str:
    return f"{ORIGEN_MERCADO}: {n} precios{' premium' if premium else ''} en {archivo}"


def _origenes(mercado: pd.DataFrame, otros: pd.DataFrame | None) -> list[tuple]:
    """Por trek: (clave, datos del trek, {nivel: (precio, origen_precio)}).

    origen_precio dice de dónde sale el precio y con cuántas observaciones."""
    estandar, _ = precios_estandar(mercado)
    premium, _ = precios_premium(mercado, estandar)
    n_estandar, n_premium = _n_precios(mercado, False), _n_precios(mercado, True)
    filas = []
    for clave, trek in TREKS.items():
        precio_e, origen_e = estandar[clave]
        if origen_e == ORIGEN_MERCADO:
            base_e = f"estándar = mediana de {n_estandar[clave]} precios en {ARCHIVO_MERCADO}"
            texto_e = _origen_mediana(n_estandar[clave], ARCHIVO_MERCADO)
        else:
            base_e = "estándar = el de 5 días − 10 %"
            texto_e = f"{ORIGEN_SUPUESTO}: {base_e}"
        precio_p, origen_p = premium[clave]
        texto_p = (_origen_mediana(n_premium.get(clave, 0), ARCHIVO_MERCADO, premium=True)
                   if origen_p == ORIGEN_MERCADO else f"{ORIGEN_SUPUESTO}: estándar + 60 % ({base_e})")
        filas.append((clave, trek, {
            "economico": (redondear(precio_e * (1 - DESCUENTO_ECONOMICO)), f"{ORIGEN_SUPUESTO}: estándar − 20 % ({base_e})"),
            "estandar": (precio_e, texto_e),
            "premium": (precio_p, texto_p),
        }))
    if otros is not None:
        for clave, (precio_e, n) in precios_otros(otros)[0].items():
            base_e = f"estándar = mediana de {n} precios en {ARCHIVO_OTROS}"
            filas.append((clave, OTROS_TREKS[clave], {
                "economico": (redondear(precio_e * (1 - DESCUENTO_ECONOMICO)), f"{ORIGEN_SUPUESTO}: estándar − 20 % ({base_e})"),
                "estandar": (precio_e, _origen_mediana(n, ARCHIVO_OTROS)),
                # Ese archivo no tiene el nivel de cada precio: el premium siempre es supuesto.
                "premium": (redondear(precio_e * (1 + RECARGO_PREMIUM)), f"{ORIGEN_SUPUESTO}: estándar + 60 % ({base_e})"),
            }))
    return filas


def generar_tarifario(mercado: pd.DataFrame, otros: pd.DataFrame | None = None) -> pd.DataFrame:
    filas = []
    for clave, trek, base in _origenes(mercado, otros):
        niveles = NIVELES_POR_ESTILO[trek["estilo"]]
        for nivel, datos in niveles.items():
            precio_2, origen = base[nivel]
            filas.append({
                "trek_id": trek["trek_id"],
                "ruta": trek["ruta"],
                "trek": trek["nombre"],
                "dias": clave[1],
                "nivel": nivel,
                "precio_usd_pp_grupo_2": precio_2,
                "precio_usd_pp_grupo_3a4": redondear(precio_2 * (1 - DESCUENTO_GRUPO_3A4)),
                "precio_usd_pp_grupo_5mas": redondear(precio_2 * (1 - DESCUENTO_GRUPO_5MAS)),
                "tamano_max_grupo": datos["tamano_max_grupo"],
                "requiere_permiso_camino_inca": trek["requiere_permiso_camino_inca"],
                "meses_no_disponible": trek["meses_no_disponible"],
                "incluye": f"{INCLUYE_BASE[trek['ruta']]}; {datos['incluye']}",
                "no_incluye": datos["no_incluye"],
                # Huayna Picchu y Vistadome solo se suman a treks que llegan a Machu Picchu.
                "llega_a_machu_picchu": "no" if trek["estilo"] == "campamento_sin_machu_picchu" else "si",
                # Origen del precio para 2 personas. Los de 3-4 y 5+ siempre aplican los descuentos supuestos.
                "origen_precio": origen,
            })
    return pd.DataFrame(filas)


EXTRAS = {
    "huayna_picchu": {"nombre": "Ingreso a Huayna Picchu", "niveles": "economico;estandar;premium"},
    "vistadome": {"nombre": "Mejora a tren Vistadome en el regreso", "niveles": "economico;estandar"},
}


def generar_extras(extras_mercado: pd.DataFrame) -> pd.DataFrame:
    """Precio de cada extra = mediana del mercado redondeada a múltiplos de 5."""
    medianas = validos(extras_mercado).groupby("extra")["precio_usd_pp"].agg(["median", "count"])
    return pd.DataFrame([
        {
            "extra_id": extra_id,
            "extra": datos["nombre"],
            "precio_usd_pp": redondear(medianas.loc[extra_id, "median"], paso=5),
            "aplica_a_niveles": datos["niveles"],
            "n_precios_mercado": int(medianas.loc[extra_id, "count"]),
        }
        for extra_id, datos in EXTRAS.items()
    ])


if __name__ == "__main__":
    mercado = pd.read_csv(DATA / "precios_mercado.csv")
    print(f"Publicaciones registradas: {len(mercado)} "
          f"(excluidas del análisis: {(mercado['incluir_en_analisis'] == 'no').sum()})\n")
    print(resumen(mercado).to_string(index=False))
    print("\nSin la opción premium:")
    print(resumen(mercado[mercado["nivel_aprox"] != "premium"]).to_string(index=False))
    print("\nPor tipo de fuente (filas válidas):")
    print(validos(mercado).groupby(["trek", "dias", "tipo_fuente"])["precio_usd_pp"]
          .agg(n="count", minimo="min", mediana="median", maximo="max").to_string())
    print("\nSin premium, solo precios publicados:")
    print(resumen(mercado[(mercado["nivel_aprox"] != "premium")
                          & (mercado["tipo_fuente"] == "precio publicado")]).to_string(index=False))
    print("\nBolsa de dormir incluida:")
    print(mercado["incluye_bolsa_dormir"].value_counts().to_string())

    estandar, notas = precios_estandar(mercado)
    notas += precios_premium(mercado, estandar)[1]
    print("\nReglas aplicadas al precio estándar y premium:")
    for nota in notas:
        print(" -", nota)

    otros = pd.read_csv(DATA / ARCHIVO_OTROS)
    _, notas_otros, fuera = precios_otros(otros)
    print(f"\nOtros treks ({ARCHIVO_OTROS}, mínimo {MIN_PRECIOS_TREK} precios por trek):")
    for nota in notas_otros:
        print(" -", nota)
    print("Quedaron fuera:", "; ".join(fuera) if fuera else "ninguno")

    tarifario = generar_tarifario(mercado, otros)
    tarifario.to_csv(DATA / "tarifario_demo.csv", index=False)
    print("\nTarifario generado en data/tarifario_demo.csv:")
    print(tarifario[["trek_id", "nivel", "precio_usd_pp_grupo_2", "precio_usd_pp_grupo_3a4",
                     "precio_usd_pp_grupo_5mas"]].to_string(index=False))

    extras = generar_extras(pd.read_csv(DATA / "extras_mercado.csv"))
    extras.to_csv(DATA / "extras_demo.csv", index=False)
    print("\nExtras generados en data/extras_demo.csv:")
    print(extras.to_string(index=False))
