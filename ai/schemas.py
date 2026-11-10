"""Esquemas de las salidas estructuradas del modelo.

Cada clase describe exactamente qué campos debe devolver el modelo y de qué tipo.
El mismo esquema sirve para dos cosas:
1. Se le entrega al proveedor (Gemini o Claude) para que la respuesta salga en
   ese formato JSON y no como texto libre.
2. pydantic valida lo que vuelve: si falta un campo obligatorio o un valor no está
   permitido (por ejemplo, un trek que no existe), lanza un error en vez de dejar
   pasar un dato raro al resto del código.

Las descripciones de cada campo (Field(description=...)) también las lee el modelo:
son parte de las instrucciones.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

# Códigos fijos: coinciden con data/knowledge (ai/knowledge.py) y con la columna
# "ruta" del tarifario (core/cotizacion.py). Así el modelo no puede inventar un trek.
CodigoTrek = Literal["salkantay", "camino_inca", "camino_inca_corto", "lares", "choquequirao", "inca_jungle"]
Nivel = Literal["economico", "estandar", "premium"]
Extra = Literal["huayna_picchu", "vistadome"]


class PerfilTurista(BaseModel):
    """Lo que el modelo extrae de la consulta del turista. No calcula nada."""

    idioma: str = Field(description="Código ISO 639-1 del idioma en que escribió el turista, por ejemplo 'en', 'es', 'pt'.")
    num_personas: Optional[int] = Field(None, ge=1, description="Número de viajeros; null si no lo dice.")
    mes_viaje: Optional[int] = Field(None, ge=1, le=12, description="Mes del viaje (1 a 12); null si no lo dice. 'Late March' es 3.")
    fecha_texto: Optional[str] = Field(None, description="Las fechas tal como las escribió el turista; null si no da ninguna.")
    dias_disponibles: Optional[int] = Field(None, ge=1, description="Días que tiene para el trek, si los menciona. Si duda entre 4 o 5, pon el mayor.")
    treks_de_interes: list[CodigoTrek] = Field(
        default_factory=list,
        description="Treks que menciona. Si pide llegar a Machu Picchu caminando sin nombrar una ruta, pon 'salkantay' y 'camino_inca'.",
    )
    nivel_preferido: Optional[Nivel] = Field(None, description="Nivel de servicio si lo pide o lo da a entender claramente; null si no.")
    presupuesto_usd_pp: Optional[float] = Field(None, description="Presupuesto por persona en dólares, solo si lo dice.")
    extras_de_interes: list[Extra] = Field(default_factory=list, description="Extras que pide: Huayna Picchu o tren Vistadome.")
    temas_consulta: list[str] = Field(
        default_factory=list,
        description="Temas que pregunta, en español y en pocas palabras: 'precio', 'qué incluye', 'altura', 'permisos', 'clima'.",
    )
    datos_faltantes: list[str] = Field(
        default_factory=list,
        description="Datos que faltan para cotizar con precisión, en español: 'fecha exacta', 'nivel de servicio', 'número de personas'.",
    )


class BorradorRespuesta(BaseModel):
    """El mensaje que el vendedor revisará antes de enviarlo por WhatsApp."""

    idioma: str = Field(description="Código ISO 639-1 del idioma en que está escrito mensaje_para_cliente.")
    mensaje_para_cliente: str = Field(description="Un solo mensaje de WhatsApp, en el idioma del turista, de menos de 150 palabras.")
    preguntas_al_turista: list[str] = Field(
        default_factory=list, max_length=2,
        description="Las 1 o 2 preguntas con las que termina el mensaje, copiadas tal cual.",
    )
    advertencias_para_agencia: list[str] = Field(
        default_factory=list,
        description="Notas internas en español para el vendedor: qué debe verificar o confirmar antes de enviar.",
    )
