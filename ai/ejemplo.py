"""Ejemplo guardado: el resultado completo de una consulta real al modelo, en data/ejemplo_guardado.json.

Sirve para dos cosas en el demo público:
1. El botón "Usar mensaje de ejemplo" muestra este resultado sin llamar a la API (no gasta cuota).
2. Si ni el modelo principal ni el de respaldo pueden responder (sin cuota o saturados),
   la app muestra este resultado con un aviso claro, en vez de quedar sin respuesta.

El archivo se genera una sola vez con:  python scripts/guardar_ejemplo.py
No tiene datos personales: la consulta es la de la prueba de cliente misterioso, sin nombres ni teléfonos.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from datetime import date
from pathlib import Path

import pandas as pd

from ai.knowledge import BaseConocimiento, Fragmento
from ai.llm import LLM, ModelosNoDisponiblesError, Uso
from ai.pipeline import Resultado, procesar_consulta
from ai.schemas import BorradorRespuesta, PerfilTurista
from core.cotizacion import OpcionCotizada

RUTA_EJEMPLO = Path(__file__).resolve().parents[1] / "data" / "ejemplo_guardado.json"
AVISO_SIN_CUOTA = "Ejemplo guardado de una consulta real al modelo: se acabó la cuota gratuita de hoy"


def resultado_a_dict(resultado: Resultado, consulta: str, fecha: str | None = None) -> dict:
    return {
        "descripcion": "Resultado completo de una consulta real al modelo, guardado para el demo. Sin datos personales.",
        "fecha": fecha or date.today().isoformat(),
        "consulta": consulta,
        "perfil": resultado.perfil.model_dump(),
        "opciones": [asdict(o) for o in resultado.opciones],
        "fragmentos": [asdict(f) for f in resultado.fragmentos],
        "aviso": resultado.aviso,
        "borrador": resultado.borrador.model_dump(),
        "precios_no_autorizados": resultado.precios_no_autorizados,
        "advertencias": resultado.advertencias,
        "uso": asdict(resultado.uso),
    }


def resultado_desde_dict(datos: dict) -> Resultado:
    opciones = []
    for o in datos["opciones"]:
        o = dict(o, extras=[tuple(e) for e in o.get("extras", [])])  # JSON guarda las tuplas como listas
        opciones.append(OpcionCotizada(**o))
    return Resultado(
        perfil=PerfilTurista.model_validate(datos["perfil"]),
        opciones=opciones,
        fragmentos=[Fragmento(**f) for f in datos["fragmentos"]],
        aviso=datos["aviso"],
        borrador=BorradorRespuesta.model_validate(datos["borrador"]),
        precios_no_autorizados=list(datos["precios_no_autorizados"]),
        advertencias=list(datos["advertencias"]),
        uso=Uso(**datos["uso"]),
    )


def guardar_ejemplo(resultado: Resultado, consulta: str, ruta: Path = RUTA_EJEMPLO) -> None:
    ruta.write_text(json.dumps(resultado_a_dict(resultado, consulta), ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")


def cargar_ejemplo(ruta: Path = RUTA_EJEMPLO) -> tuple[Resultado, dict]:
    """Devuelve (resultado, datos del archivo): los datos traen la consulta y la fecha."""
    datos = json.loads(Path(ruta).read_text(encoding="utf-8"))
    return resultado_desde_dict(datos), datos


def responder_con_respaldo(consulta: str, llm: LLM, base: BaseConocimiento, tarifario: pd.DataFrame,
                           extras: pd.DataFrame | None = None, agencia: str | None = None,
                           ruta_ejemplo: Path = RUTA_EJEMPLO) -> tuple[Resultado, bool]:
    """Último eslabón de la cadena: modelo principal -> respaldo -> ejemplo guardado.

    Devuelve (resultado, es_ejemplo). es_ejemplo = True si ningún modelo pudo responder
    y se devolvió el ejemplo guardado.
    """
    argumentos = {"agencia": agencia} if agencia else {}
    try:
        return procesar_consulta(consulta, llm, base, tarifario, extras, **argumentos), False
    except ModelosNoDisponiblesError:
        resultado, _ = cargar_ejemplo(ruta_ejemplo)
        return resultado, True
