"""Evaluación reducida con el modelo real: pocas consultas, resultados honestos en docs/evaluacion.md.

Uso:
    python scripts/evaluar.py C09 C08            # solo esas consultas (2 llamadas al modelo cada una)
    python scripts/evaluar.py --sin-escribir C09 # muestra el resultado y no toca docs/evaluacion.md
    python scripts/evaluar.py --seguir C10 C17   # agrega a lo ya guardado en docs/evaluacion.md (por JSON)

Cuida la cuota gratuita: 2 llamadas por consulta. Si aparece un error de cuota (429) o de modelo,
se detiene de inmediato, NO reintenta con otra consulta y lo deja anotado.

Qué se comprueba (todo en código, sin llamar al modelo otra vez):
  - controles de ai/pipeline.py (precios fuera de cotización, 150 palabras, idioma, depósito, cupo, pregunta...)
  - idioma detectado vs. el esperado del CSV, personas, mes y treks del perfil vs. el CSV
  - qué modelo respondió (principal, respaldo) o si hubo que usar el ejemplo guardado
El "es correcto" lo decide el script solo con esas reglas; la lectura del mensaje (¿advierte lo que debía?)
se anota aparte, a mano, en docs/evaluacion.md.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from ai import prompts  # noqa: E402
from ai.knowledge import BaseConocimiento  # noqa: E402
from ai.llm import ModelosNoDisponiblesError, crear_llm  # noqa: E402
from ai.pipeline import contar_palabras, controlar_borrador, procesar_consulta  # noqa: E402
from core.cotizacion import cargar_extras, cargar_tarifario  # noqa: E402

CSV = RAIZ / "evaluacion" / "consultas_evaluacion.csv"
SALIDA_JSON = RAIZ / "docs" / "evaluacion_datos.json"
SALIDA_MD = RAIZ / "docs" / "evaluacion.md"
POR_DEFECTO = ["C09", "C08", "C10", "C17", "C16"]  # en/es/pt; con y sin trek; con y sin fecha relativa


def _vacio(x) -> bool:
    return x is None or (isinstance(x, float) and pd.isna(x)) or x == ""


def evaluar_una(id_: str, fila, llm, base, tarifario, extras) -> dict:
    consulta = fila["consulta"]
    r = procesar_consulta(consulta, llm, base, tarifario, extras)
    texto = r.borrador.mensaje_para_cliente
    _, controles = controlar_borrador(r.borrador, r.perfil, r.opciones)  # los controles de código, sin el modelo
    palabras = contar_palabras(texto)

    esperado_treks = sorted(t for t in str(fila["treks_esperados"]).split(";") if t and t != "nan")
    diferencias = []
    if r.perfil.idioma.lower() != fila["idioma_esperado"]:
        diferencias.append(f"idioma detectado '{r.perfil.idioma}' vs esperado '{fila['idioma_esperado']}'")
    if not _vacio(fila["num_personas_esperado"]) and r.perfil.num_personas != int(fila["num_personas_esperado"]):
        diferencias.append(f"personas {r.perfil.num_personas} vs esperado {int(fila['num_personas_esperado'])}")
    if not _vacio(fila["mes_viaje_esperado"]) and r.perfil.mes_viaje != int(fila["mes_viaje_esperado"]):
        diferencias.append(f"mes {r.perfil.mes_viaje} vs esperado {int(fila['mes_viaje_esperado'])}")
    if esperado_treks and esperado_treks != ["otro"] and sorted(r.perfil.treks_de_interes) != esperado_treks:
        diferencias.append(f"treks {sorted(r.perfil.treks_de_interes)} vs esperado {esperado_treks}")

    return {
        "id": id_,
        "consulta": consulta,
        "debe_advertir": fila["debe_advertir"],
        "idioma_esperado": fila["idioma_esperado"],
        "idioma_detectado": r.perfil.idioma,
        "idioma_respuesta": r.borrador.idioma,
        "treks_perfil": list(r.perfil.treks_de_interes),
        "personas": r.perfil.num_personas,
        "mes": r.perfil.mes_viaje,
        "opciones": [{"trek_id": o.trek_id, "nivel": o.nivel, "precio_pp": o.precio_pp, "total": o.total,
                      "alternativa": o.es_alternativa} for o in r.opciones],
        "precios_no_autorizados": list(r.precios_no_autorizados),
        "palabras": palabras,
        "limite_150_ok": palabras < prompts.LIMITE_PALABRAS,
        "controles_activados": controles,
        "advertencias_modelo": list(r.borrador.advertencias_para_agencia),
        "avisos_fijos": list(r.avisos_fijos),
        "modelos": list(dict.fromkeys(r.uso.modelos)),
        "fuente": "modelo real",
        "diferencias_perfil": diferencias,
        "mensaje": texto,
        "aviso": r.aviso,
    }


def sin_controles(d: dict) -> bool:
    return not d["controles_activados"] and not d["diferencias_perfil"]


def escribir_md(datos: list[dict], detenido: str | None) -> None:
    n = len(datos)
    limpias = sum(sin_controles(d) for d in datos)
    L = ["# Evaluación reducida del asistente", "",
         f"**{limpias} de {n} consultas sin ningún control activado** (ni controles de código ni diferencias "
         "entre el perfil extraído y lo esperado en `evaluacion/consultas_evaluacion.csv`).", ""]
    if detenido:
        L += [f"> **Evaluación incompleta:** {detenido}", ""]
    L += ["## Limitaciones", "",
          f"- {n} casos no son una evaluación estadística: no se pueden sacar porcentajes ni comparar versiones con esto.",
          "- Es una sola corrida con temperatura 0.2: otra corrida puede dar otro resultado.",
          "- Se evaluó con el modelo real, con el tarifario y la base de conocimiento de demostración.",
          "- \"Sin controles\" no equivale a \"respuesta buena\": los controles solo miran precios, largo, idioma, "
          "depósito, cupo y pregunta final. Lo que el mensaje debía advertir se lee a mano (columna Lectura).",
          "- La lectura a mano la hizo quien armó la evaluación, no un evaluador independiente.", "",
          "## Resultados por consulta", ""]
    for d in datos:
        L += [f"### {d['id']} — {'sin controles' if sin_controles(d) else 'CON FALLAS'}", "",
              f"- **Consulta:** {d['consulta']}",
              f"- **Idioma:** detectado `{d['idioma_detectado']}` (esperado `{d['idioma_esperado']}`); "
              f"respuesta en `{d['idioma_respuesta']}`",
              f"- **Trek:** {', '.join(d['treks_perfil']) or 'ninguno en el perfil'}; personas {d['personas']}; mes {d['mes']}",
              "- **Opciones cotizadas por el código:** " + (
                  "; ".join(f"{o['trek_id']} {o['nivel']} US$ {o['precio_pp']} pp / total US$ {o['total']}"
                            f"{' (alternativa)' if o['alternativa'] else ''}" for o in d["opciones"]) or "ninguna"),
              f"- **Precios no autorizados (montos inventados):** {d['precios_no_autorizados'] or 'ninguno'}",
              f"- **Límite de 150 palabras:** {d['palabras']} palabras → {'cumple' if d['limite_150_ok'] else 'FALLA'}",
              f"- **Controles activados:** {'; '.join(d['controles_activados']) or 'ninguno'}",
              f"- **Diferencias con lo esperado:** {'; '.join(d['diferencias_perfil']) or 'ninguna'}",
              f"- **Quién respondió:** {', '.join(d['modelos'])} ({d['fuente']})",
              f"- **Debía advertir (CSV):** {d['debe_advertir']}",
              f"- **Advertencias del modelo para la agencia:** {'; '.join(d['advertencias_modelo']) or 'ninguna'}",
              "- **Lectura a mano:** _pendiente_", "",
              "Mensaje generado:", ""] + ["> " + linea for linea in d["mensaje"].splitlines()] + [""]
    SALIDA_MD.write_text("\n".join(L), encoding="utf-8")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    seguir, escribir = "--seguir" in sys.argv, "--sin-escribir" not in sys.argv
    ids = args or POR_DEFECTO
    evaluacion = pd.read_csv(CSV).set_index("id")
    llm = crear_llm()
    base = BaseConocimiento(RAIZ / "data" / "knowledge")
    tarifario = cargar_tarifario(RAIZ / "data" / "tarifario_demo.csv")
    extras = cargar_extras(RAIZ / "data" / "extras_demo.csv")

    datos = json.loads(SALIDA_JSON.read_text(encoding="utf-8")) if seguir and SALIDA_JSON.exists() else []
    detenido = None
    for id_ in ids:
        try:
            d = evaluar_una(id_, evaluacion.loc[id_], llm, base, tarifario, extras)
        except ModelosNoDisponiblesError as e:  # 429 diario o 503 en los dos modelos: parar, no reintentar
            detenido = f"se detuvo en {id_}: {e} Se usaría el ejemplo guardado; no se evaluó."
            break
        except Exception as e:  # noqa: BLE001 - cualquier error del modelo: parar y reportarlo
            detenido = f"se detuvo en {id_}: {type(e).__name__}: {e}"
            break
        datos.append(d)
        print(f"{id_}: {'sin controles' if sin_controles(d) else 'CON FALLAS'} | modelos {d['modelos']} | "
              f"{d['palabras']} palabras | controles {d['controles_activados']} | dif {d['diferencias_perfil']}")
    if detenido:
        print("DETENIDO:", detenido)
    if escribir and datos:
        SALIDA_JSON.write_text(json.dumps(datos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        escribir_md(datos, detenido)


if __name__ == "__main__":
    main()
