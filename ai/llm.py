"""Conexión con el modelo de lenguaje.

El resto del código solo conoce la interfaz `LLM`: un método `estructurado()` que
recibe instrucciones, un mensaje y un esquema de pydantic, y devuelve un objeto de
ese esquema ya validado. Qué proveedor responde se elige con la variable
LLM_PROVIDER, sin tocar nada más:

    LLM_PROVIDER=gemini   (por defecto)  clave en GEMINI_API_KEY, modelo en GEMINI_MODEL
    LLM_PROVIDER=claude                  clave en ANTHROPIC_API_KEY, modelo en ANTHROPIC_MODEL

Las claves se leen del entorno (o del archivo .env, que no se sube al repositorio).
Nunca se escriben en el código.
"""
from __future__ import annotations

import os
import random
import time
from dataclasses import dataclass
from typing import Callable, Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)
R = TypeVar("R")

MODELO_GEMINI = "gemini-3.5-flash"  # gemini-2.5-flash ya no se habilita a cuentas nuevas
MODELO_CLAUDE = "claude-haiku-5-5"

# Reintentos ante el límite de la capa gratuita (429). Las esperas crecen: 10, 20, 40 s.
INTENTOS = 4
ESPERA_INICIAL_S = 10.0
TIEMPO_LIMITE_S = 90       # por llamada


@dataclass
class Uso:
    tokens_entrada: int = 0
    tokens_salida: int = 0

    def sumar(self, otro: "Uso") -> "Uso":
        return Uso(self.tokens_entrada + otro.tokens_entrada, self.tokens_salida + otro.tokens_salida)


class LimiteDiarioError(RuntimeError):
    """Se acabó la cuota diaria de la capa gratuita: esperar unos segundos no sirve."""


class LLM(Protocol):
    def estructurado(self, sistema: str, mensaje: str, esquema: type[T]) -> tuple[T, Uso]: ...


def con_reintentos(llamada: Callable[[], R], es_reintentable: Callable[[Exception], bool],
                   intentos: int = INTENTOS, espera_inicial: float = ESPERA_INICIAL_S,
                   dormir: Callable[[float], None] = time.sleep) -> R:
    """Ejecuta `llamada` y, si falla con un error reintentable (429), espera y vuelve a intentar.

    Cualquier otro error (clave inválida, esquema mal hecho) se lanza de inmediato:
    reintentarlo no lo arreglaría. `dormir` se puede reemplazar en las pruebas.
    """
    for intento in range(intentos):
        try:
            return llamada()
        except Exception as error:  # noqa: BLE001 - se filtra con es_reintentable
            if not es_reintentable(error) or intento == intentos - 1:
                raise
            dormir(espera_inicial * 2 ** intento + random.uniform(0, 1))
    raise RuntimeError("inalcanzable")


class GeminiLLM:
    """Gemini con salida estructurada: response_schema = el esquema de pydantic."""

    def __init__(self, api_key: str | None = None, modelo: str | None = None):
        from google import genai  # se importa aquí para que las pruebas no lo necesiten
        from google.genai import types

        clave = api_key or os.getenv("GEMINI_API_KEY")
        if not clave:
            raise RuntimeError("Falta GEMINI_API_KEY. Ponla en el archivo .env (ver .env.example).")
        # Tiempo límite por llamada (en milisegundos): sin él, una llamada colgada espera para siempre.
        self._cliente = genai.Client(api_key=clave, http_options=types.HttpOptions(timeout=TIEMPO_LIMITE_S * 1000))
        self.modelo = modelo or os.getenv("GEMINI_MODEL") or MODELO_GEMINI

    @staticmethod
    def es_reintentable(error: Exception) -> bool:
        from google.genai import errors

        # 429: límite de solicitudes por minuto de la capa gratuita (el diario no: ver es_limite_diario).
        # 503: modelo sobrecargado, también temporal.
        if isinstance(error, errors.APIError):
            return error.code == 503 or (error.code == 429 and not GeminiLLM.es_limite_diario(error))
        # Cortes de red ("Server disconnected without sending a response"): también temporales.
        return type(error).__module__.split(".")[0] in ("httpx", "httpx2", "httpcore", "httpcore2")

    @staticmethod
    def es_limite_diario(error: Exception) -> bool:
        """429 por la cuota diaria (p. ej. 20 solicitudes por día y modelo en la capa gratuita)."""
        return getattr(error, "code", None) == 429 and "PerDay" in str(error)

    def estructurado(self, sistema: str, mensaje: str, esquema: type[T]) -> tuple[T, Uso]:
        from google.genai import types

        config = types.GenerateContentConfig(
            system_instruction=sistema,
            response_mime_type="application/json",
            response_schema=esquema,
            temperature=0.2,
        )
        try:
            respuesta = con_reintentos(
                lambda: self._cliente.models.generate_content(model=self.modelo, contents=mensaje, config=config),
                self.es_reintentable,
            )
        except Exception as error:
            if self.es_limite_diario(error):
                raise LimiteDiarioError(
                    f"Se acabó la cuota diaria gratuita de Gemini para el modelo {self.modelo}. "
                    "Vuelve a intentar mañana o cambia GEMINI_MODEL en el archivo .env."
                ) from error
            raise
        resultado = respuesta.parsed if isinstance(respuesta.parsed, esquema) else None
        if resultado is None:
            if not respuesta.text:
                raise RuntimeError("Gemini no devolvió una salida estructurada.")
            resultado = esquema.model_validate_json(respuesta.text)
        meta = respuesta.usage_metadata
        uso = Uso(getattr(meta, "prompt_token_count", 0) or 0, getattr(meta, "candidates_token_count", 0) or 0)
        return resultado, uso


class ClaudeLLM:
    """Claude con salida estructurada: messages.parse(output_format=esquema)."""

    def __init__(self, api_key: str | None = None, modelo: str | None = None):
        import anthropic

        clave = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not clave:
            raise RuntimeError("Falta ANTHROPIC_API_KEY. Ponla en el archivo .env (ver .env.example).")
        # max_retries=0: los reintentos los maneja con_reintentos, igual que con Gemini.
        self._cliente = anthropic.Anthropic(api_key=clave, max_retries=0)
        self.modelo = modelo or os.getenv("ANTHROPIC_MODEL") or MODELO_CLAUDE

    @staticmethod
    def es_reintentable(error: Exception) -> bool:
        import anthropic

        return isinstance(error, (anthropic.RateLimitError, anthropic.InternalServerError))

    def estructurado(self, sistema: str, mensaje: str, esquema: type[T]) -> tuple[T, Uso]:
        respuesta = con_reintentos(
            lambda: self._cliente.messages.parse(
                model=self.modelo,
                max_tokens=4000,
                system=sistema,
                messages=[{"role": "user", "content": mensaje}],
                output_format=esquema,
            ),
            self.es_reintentable,
        )
        if respuesta.stop_reason == "refusal" or respuesta.parsed_output is None:
            raise RuntimeError(f"Claude no devolvió una salida estructurada (stop_reason={respuesta.stop_reason}).")
        uso = Uso(respuesta.usage.input_tokens, respuesta.usage.output_tokens)
        return respuesta.parsed_output, uso


PROVEEDORES = {"gemini": GeminiLLM, "claude": ClaudeLLM}


def crear_llm(proveedor: str | None = None) -> LLM:
    """Crea el modelo según LLM_PROVIDER (gemini por defecto). Lee el .env si existe."""
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass
    nombre = (proveedor or os.getenv("LLM_PROVIDER") or "gemini").strip().lower()
    if nombre not in PROVEEDORES:
        raise ValueError(f"LLM_PROVIDER='{nombre}' no existe. Opciones: {', '.join(PROVEEDORES)}.")
    return PROVEEDORES[nombre]()
