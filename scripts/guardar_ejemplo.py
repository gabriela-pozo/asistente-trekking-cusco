"""Corre UNA vez la consulta del cliente misterioso con el modelo principal y guarda el resultado.

Uso:  python scripts/guardar_ejemplo.py

Hace 2 llamadas reales a la API (extraer el perfil y redactar). Desactiva el respaldo
a propósito: el ejemplo debe venir del modelo principal (GEMINI_MODEL).
Escribe data/ejemplo_guardado.json, que usa la app cuando no hay cuota.
"""
from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from dotenv import load_dotenv  # noqa: E402

from ai.ejemplo import RUTA_EJEMPLO, guardar_ejemplo  # noqa: E402
from ai.knowledge import BaseConocimiento  # noqa: E402
from ai.llm import GeminiLLM  # noqa: E402
from ai.pipeline import procesar_consulta  # noqa: E402
from core.cotizacion import cargar_extras, cargar_tarifario  # noqa: E402

CONSULTA = ("Hi! We are 2 friends planning to visit Cusco in late March. Is the Salkantay trek to Machu Picchu "
            "possible in 4 or 5 days? How much would it cost per person and what is included? Thanks!")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    load_dotenv(RAIZ / ".env")
    llm = GeminiLLM(respaldo="")  # sin respaldo: solo el modelo principal
    resultado = procesar_consulta(
        CONSULTA, llm, BaseConocimiento(RAIZ / "data" / "knowledge"),
        cargar_tarifario(RAIZ / "data" / "tarifario_demo.csv"), cargar_extras(RAIZ / "data" / "extras_demo.csv"),
    )
    guardar_ejemplo(resultado, CONSULTA)
    print(f"Guardado en {RUTA_EJEMPLO.relative_to(RAIZ)}")
    print(f"Respondió: {resultado.uso.modelos_que_respondieron()}")
    print(f"Tokens: entrada {resultado.uso.tokens_entrada}, salida {resultado.uso.tokens_salida}")
    print(f"\nBORRADOR ({len(resultado.borrador.mensaje_para_cliente.split())} palabras):")
    print(resultado.borrador.mensaje_para_cliente)
    print("\nADVERTENCIAS:", resultado.advertencias or "ninguna")


if __name__ == "__main__":
    main()
