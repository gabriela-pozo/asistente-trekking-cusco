"""Datos de ruta para el mapa. Funciones puras, sin Streamlit.

Lee los CSV de data/rutas/ (coordenadas de OpenStreetMap/Wikipedia, ODbL). No inventa nada:
si un trek no tiene archivo, o el archivo no sirve, devuelve None.
"""
from __future__ import annotations

import csv
import math
from dataclasses import dataclass, field
from pathlib import Path

CARPETA_RUTAS = Path(__file__).resolve().parent.parent / "data" / "rutas"
ATRIBUCION = "© OpenStreetMap contributors (ODbL)"
TIPOS = {"inicio", "campamento", "paso", "sitio", "fin"}


@dataclass(frozen=True)
class Punto:
    dia: int
    orden: int
    lugar: str
    latitud: float
    longitud: float
    altitud_m: int | None
    tipo: str


@dataclass(frozen=True)
class Ruta:
    ruta: str  # "salkantay", "camino_inca", "lares"
    archivo: str
    puntos: tuple[Punto, ...] = field(default_factory=tuple)

    @property
    def dias_itinerario(self) -> int:
        return int(archivo_dias(self.archivo)) if archivo_dias(self.archivo) else 0

    def de_tipo(self, *tipos: str) -> list[Punto]:
        return [p for p in self.puntos if p.tipo in tipos]


def archivo_dias(archivo: str) -> str:
    """'salkantay_5d.csv' -> '5'; '' si no se puede leer."""
    base = archivo.rsplit(".", 1)[0]
    cola = base.rsplit("_", 1)[-1]
    return cola[:-1] if cola.endswith("d") and cola[:-1].isdigit() else ""


def _numero(texto: str | None) -> float | None:
    try:
        return float(texto) if texto not in (None, "") else None
    except ValueError:
        return None


def _fila_a_punto(fila: dict) -> Punto | None:
    lat, lon = _numero(fila.get("latitud")), _numero(fila.get("longitud"))
    if lat is None or lon is None or not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None
    alt = _numero(fila.get("altitud_m"))
    try:
        dia, orden = int(fila["dia"]), int(fila["orden"])
    except (KeyError, TypeError, ValueError):
        return None
    return Punto(dia, orden, (fila.get("lugar") or "").strip(), lat, lon,
                 int(alt) if alt is not None else None, (fila.get("tipo") or "").strip())


def archivos_de_ruta(ruta: str, carpeta: Path = CARPETA_RUTAS) -> list[Path]:
    """Archivos '<ruta>_<n>d.csv' de la carpeta, ordenados por nombre."""
    try:
        return sorted(p for p in carpeta.glob(f"{ruta}_*d.csv") if archivo_dias(p.name))
    except OSError:
        return []


def cargar_ruta(ruta: str | None, carpeta: Path = CARPETA_RUTAS) -> Ruta | None:
    """Ruta de un trek ('salkantay', 'camino_inca', 'lares'), o None si no hay datos utilizables."""
    if not ruta or not ruta.replace("_", "").isalnum():
        return None
    for archivo in archivos_de_ruta(ruta, carpeta):
        try:
            with archivo.open(encoding="utf-8", newline="") as f:
                puntos = [p for p in (_fila_a_punto(fila) for fila in csv.DictReader(f)) if p]
        except (OSError, UnicodeDecodeError, csv.Error):
            continue
        puntos.sort(key=lambda p: p.orden)
        if len(puntos) >= 2:
            return Ruta(ruta, archivo.name, tuple(puntos))
    return None


def treks_con_mapa(carpeta: Path = CARPETA_RUTAS) -> list[str]:
    """Nombres de ruta con datos utilizables (para informes y pruebas)."""
    try:
        nombres = {p.name.rsplit("_", 1)[0] for p in carpeta.glob("*_*d.csv")}
    except OSError:
        return []
    return sorted(n for n in nombres if cargar_ruta(n, carpeta))


def km_entre(a: Punto, b: Punto) -> float:
    """Distancia en línea recta (haversine) entre dos puntos, en km."""
    f1, f2 = math.radians(a.latitud), math.radians(b.latitud)
    df, dl = f2 - f1, math.radians(b.longitud - a.longitud)
    h = math.sin(df / 2) ** 2 + math.cos(f1) * math.cos(f2) * math.sin(dl / 2) ** 2
    return 2 * 6371.0088 * math.asin(math.sqrt(h))


def distancia_recta_km(ruta: Ruta | None) -> float | None:
    """Suma de tramos en línea recta entre puntos consecutivos. Es un MÍNIMO: el sendero real es más largo.
    Incluye tramos en vehículo si el itinerario los trae; por eso solo se usa como referencia."""
    if ruta is None or len(ruta.puntos) < 2:
        return None
    return sum(km_entre(a, b) for a, b in zip(ruta.puntos, ruta.puntos[1:]))


def desnivel(ruta: Ruta | None) -> dict | None:
    """Subida y bajada acumuladas entre los puntos que SÍ tienen altitud (en orden).

    None si hay menos de 3 altitudes. Con huecos en los datos es un cálculo parcial; por eso devuelve
    cuántos puntos se usaron.
    """
    if ruta is None:
        return None
    alts = [p.altitud_m for p in ruta.puntos if p.altitud_m is not None]
    if len(alts) < 3:
        return None
    subida = sum(max(b - a, 0) for a, b in zip(alts, alts[1:]))
    bajada = sum(max(a - b, 0) for a, b in zip(alts, alts[1:]))
    return {"subida_m": subida, "bajada_m": bajada, "maxima_m": max(alts), "minima_m": min(alts),
            "puntos_con_altitud": len(alts), "puntos": len(ruta.puntos)}


def perfil_altitud(ruta: Ruta | None) -> list[tuple[str, float, int]] | None:
    """(lugar, km acumulados en línea recta, altitud) de los puntos con altitud; None si hay menos de 3."""
    if ruta is None:
        return None
    acumulado, previo, salida = 0.0, None, []
    for p in ruta.puntos:
        if previo is not None:
            acumulado += km_entre(previo, p)
        previo = p
        if p.altitud_m is not None:
            salida.append((p.lugar, acumulado, p.altitud_m))
    return salida if len(salida) >= 3 else None


def enlace_google_maps(ruta: Ruta | None) -> str | None:
    """URL de búsqueda por coordenadas del primer punto de tipo 'inicio'; None si no hay."""
    if ruta is None:
        return None
    inicio = ruta.de_tipo("inicio")
    if not inicio:
        return None
    p = inicio[0]
    return f"https://www.google.com/maps/search/?api=1&query={p.latitud:.5f},{p.longitud:.5f}"
