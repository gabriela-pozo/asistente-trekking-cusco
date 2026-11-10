"""Corre el flujo completo con el modelo real y muestra cada paso.

Uso:
    python scripts/probar_consultas.py                 # consultas de ejemplo
    python scripts/probar_consultas.py C02 C18         # consultas de evaluacion/consultas_evaluacion.csv
    python scripts/probar_consultas.py "Hi! ..."       # una consulta escrita a mano

Usa el proveedor de LLM_PROVIDER (gemini por defecto) y la clave del .env.
Cada consulta hace 2 llamadas al modelo.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from ai.knowledge import BaseConocimiento  # noqa: E402
from ai.llm import crear_llm  # noqa: E402
from ai.pipeline import contar_palabras, procesar_consulta  # noqa: E402
from core.cotizacion import cargar_extras, cargar_tarifario  # noqa: E402

CLIENTE_MISTERIOSO = ("Hi! We are 2 friends planning to visit Cusco in late March. Is the Salkantay trek to Machu "
                      "Picchu possible in 4 or 5 days? How much would it cost per person and what is included? Thanks!")
POR_DEFECTO = [CLIENTE_MISTERIOSO, "C02", "C18", "C04"]


def consultas(argumentos: list[str]) -> list[tuple[str, str]]:
    evaluacion = pd.read_csv(RAIZ / "evaluacion" / "consultas_evaluacion.csv").set_index("id")
    salida = []
    for a in argumentos or POR_DEFECTO:
        if a in evaluacion.index:
            salida.append((f"{a} (esperado: {evaluacion.loc[a, 'debe_advertir']})", evaluacion.loc[a, "consulta"]))
        else:
            salida.append(("consulta escrita a mano", a))
    return salida


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    llm = crear_llm()
    base = BaseConocimiento(RAIZ / "data" / "knowledge")
    tarifario = cargar_tarifario(RAIZ / "data" / "tarifario_demo.csv")
    extras = cargar_extras(RAIZ / "data" / "extras_demo.csv")

    for titulo, consulta in consultas(sys.argv[1:]):
        r = procesar_consulta(consulta, llm, base, tarifario, extras)
        print("=" * 100)
        print(titulo)
        print("CONSULTA:", consulta)
        print("\nPERFIL:", r.perfil.model_dump_json(exclude_defaults=True))
        print("\nOPCIONES:")
        for o in r.opciones:
            print(f"  - {o.trek_id} {o.nivel}: US$ {o.precio_pp} pp, total US$ {o.total} ({o.personas} personas)"
                  f"{' [alternativa]' if o.es_alternativa else ''}")
        print("AVISO:", r.aviso)
        texto = r.borrador.mensaje_para_cliente
        print(f"\nBORRADOR ({r.borrador.idioma}, {contar_palabras(texto)} palabras):\n{texto}")
        print("\nADVERTENCIAS:")
        for a in r.advertencias or ["(ninguna)"]:
            print("  -", a)
        print(f"\nTOKENS: entrada {r.uso.tokens_entrada}, salida {r.uso.tokens_salida}")


if __name__ == "__main__":
    main()
