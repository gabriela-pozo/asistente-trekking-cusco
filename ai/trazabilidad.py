"""Trazabilidad: de dónde sale lo que dice la respuesta y en qué estado está el sistema.

Lo usan las páginas "Fuentes y verificación" y "Estado del sistema" de la app. Todo es lectura de
archivos locales: ninguna función llama a la API ni ejecuta las pruebas.
"""
from __future__ import annotations

import ast
import hashlib
import os
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd

from ai.knowledge import Fragmento, leer_cabecera

DIAS_PARA_VERIFICAR = 90  # pasado este plazo, el dato puede haber cambiado: se verifica antes de enviar
ETIQUETA_VERIFICAR = "Verificar antes de enviar"
# Dominios del Estado peruano (y normas publicadas): el resto son webs de agencias o guías.
DOMINIOS_OFICIALES = ("gob.pe", "elperuano.pe", "andina.pe", "fao.org")


def fecha_o_none(texto: str | None) -> date | None:
    try:
        return date.fromisoformat(str(texto).strip())
    except (TypeError, ValueError):
        return None


def antiguedad(actualizado: str | None, hoy: date) -> int | None:
    """Días desde la última actualización; None si la fecha falta o no se entiende."""
    fecha = fecha_o_none(actualizado)
    return None if fecha is None else (hoy - fecha).days


def hay_que_verificar(actualizado: str | None, hoy: date, limite: int = DIAS_PARA_VERIFICAR) -> bool:
    """Más de `limite` días, o sin fecha: no se puede asegurar que siga vigente."""
    dias = antiguedad(actualizado, hoy)
    return dias is None or dias > limite


def _secciones(cuerpo: str) -> int:
    return len(re.findall(r"^## ", cuerpo, flags=re.MULTILINE))


def es_oficial(url: str) -> bool:
    dominio = urlparse(url).netloc.lower()
    return any(dominio == d or dominio.endswith("." + d) for d in DOMINIOS_OFICIALES)


def dominio(url: str) -> str:
    return urlparse(url).netloc.lower().removeprefix("www.") or url


@dataclass
class FuenteUsada:
    titulo: str
    archivo: str
    actualizado: str
    dias: int | None
    verificar: bool
    fuentes: list[str]
    estado: str


def fuentes_usadas(fragmentos: list[Fragmento], hoy: date) -> list[FuenteUsada]:
    """Un renglón por fragmento que se le pasó al modelo, con su fecha y si hay que verificarlo."""
    return [FuenteUsada(f.titulo, f.archivo, f.actualizado, antiguedad(f.actualizado, hoy),
                        hay_que_verificar(f.actualizado, hoy), list(f.fuentes), f.estado)
            for f in fragmentos]


def tabla_base(carpeta: str | Path, hoy: date) -> pd.DataFrame:
    """La base de conocimiento completa: un renglón por archivo."""
    filas = []
    for ruta in sorted(Path(carpeta).glob("*.md")):
        contenido = ruta.read_text(encoding="utf-8")
        meta, cuerpo = leer_cabecera(contenido)
        actualizado = meta.get("actualizado", "")
        filas.append({
            "archivo": ruta.stem,
            "tema": meta.get("tema", ""),
            "actualizado": actualizado,
            "fragmentos": cuerpo.count("\n## ") + cuerpo.startswith("## "),
            "fuentes": list(meta.get("fuentes", [])),
            "oficiales": sum(es_oficial(u) for u in meta.get("fuentes", [])),
            "verificar": hay_que_verificar(actualizado, hoy),
            "estado": meta.get("estado", ""),
        })
    return pd.DataFrame(filas, columns=["archivo", "tema", "actualizado", "fragmentos", "fuentes", "oficiales",
                                        "verificar", "estado"])


def buscar_en_base(tabla: pd.DataFrame, texto: str) -> pd.DataFrame:
    """Filtra por archivo, tema, estado o fuente (sin distinguir mayúsculas ni tildes)."""
    texto = _sin_tildes(texto.strip().lower())
    if not texto:
        return tabla
    def coincide(fila) -> bool:
        campos = [fila["archivo"], fila["tema"], fila["estado"], *fila["fuentes"]]
        return any(texto in _sin_tildes(str(c).lower()) for c in campos)
    return tabla[tabla.apply(coincide, axis=1)] if not tabla.empty else tabla


def _sin_tildes(texto: str) -> str:
    return texto.translate(str.maketrans("áéíóúüñ", "aeiouun"))


@dataclass
class VersionBase:
    version: str        # huella de 8 caracteres del contenido: cambia si cambia cualquier archivo
    actualizada: str    # la fecha más reciente de las cabeceras
    archivos: int
    fragmentos: int


def version_base(carpeta: str | Path) -> VersionBase:
    huella = hashlib.sha256()
    fechas, archivos, fragmentos = [], 0, 0
    for ruta in sorted(Path(carpeta).glob("*.md")):
        contenido = ruta.read_text(encoding="utf-8")
        huella.update(ruta.name.encode() + b"\0" + contenido.replace("\r\n", "\n").encode())
        meta, cuerpo = leer_cabecera(contenido)
        if fecha_o_none(meta.get("actualizado")):
            fechas.append(meta["actualizado"])
        archivos += 1
        fragmentos += cuerpo.count("\n## ") + cuerpo.startswith("## ")
    return VersionBase(huella.hexdigest()[:8], max(fechas, default=""), archivos, fragmentos)


def contar_pruebas(carpeta: str | Path) -> tuple[int, int]:
    """(pruebas, archivos): funciones test_* de tests/test_*.py, leídas sin ejecutarlas."""
    pruebas = archivos = 0
    for ruta in sorted(Path(carpeta).glob("test_*.py")):
        archivos += 1
        arbol = ast.parse(ruta.read_text(encoding="utf-8"))
        pruebas += sum(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name.startswith("test")
                       for n in ast.walk(arbol))
    return pruebas, archivos


# Capa gratuita de Gemini: unas 20 solicitudes por día y modelo (ver ai/llm.py). Cada consulta hace 2 llamadas.
SOLICITUDES_DIARIAS_GEMINI = 20
LLAMADAS_POR_CONSULTA = 2


def modelos_configurados(proveedor: str) -> list[str]:
    """Los modelos que se usarían, leídos del entorno como en ai/llm.py, sin crear el cliente."""
    from ai.llm import MODELO_CLAUDE, MODELO_GEMINI, MODELO_GEMINI_RESPALDO

    if proveedor == "claude":
        return [os.getenv("ANTHROPIC_MODEL") or MODELO_CLAUDE]
    principal = os.getenv("GEMINI_MODEL") or MODELO_GEMINI
    respaldo = os.getenv("GEMINI_MODEL_RESPALDO", MODELO_GEMINI_RESPALDO)
    return [m for m in dict.fromkeys([principal, respaldo]) if m]


def consultas_restantes(proveedor: str, agotados: set[str] | None = None) -> int | None:
    """Consultas que le quedan hoy al modelo principal, solo cuando se sabe; None si no se sabe.

    La API no informa la cuota restante. Lo único seguro es el 0: el modelo ya respondió que no tiene
    cuota diaria. Con Gemini la cuota además es compartida por todos los que usan la misma clave.
    """
    principal = modelos_configurados(proveedor)[0]
    return 0 if agotados and principal in agotados else None


def referencia_cuota(proveedor: str) -> str:
    if proveedor == "claude":
        return "Claude es de pago: no hay un tope diario fijo, depende del saldo de la cuenta."
    return (f"Referencia: la capa gratuita de Gemini da unas {SOLICITUDES_DIARIAS_GEMINI} solicitudes por día y "
            f"modelo; cada consulta usa {LLAMADAS_POR_CONSULTA}, así que alcanza para unas "
            f"{SOLICITUDES_DIARIAS_GEMINI // LLAMADAS_POR_CONSULTA} consultas con cada modelo, compartidas entre "
            "todos los que usan la misma clave.")
