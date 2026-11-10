"""Fecha de hoy en Cusco y fechas relativas ("esta semana", "next month").

El modelo no sabe qué día es: si el turista escribe "esta semana", no puede saber el mes.
Por eso el código calcula la fecha de hoy en America/Lima y:
1. La pasa en los dos prompts ("Hoy es martes 10 de noviembre de 2026").
2. Si aun así el modelo deja mes_viaje vacío, la convierte en código con mes_relativo().
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone

try:
    from zoneinfo import ZoneInfo

    ZONA = ZoneInfo("America/Lima")
except Exception:  # noqa: BLE001 - sin base de zonas horarias (Windows sin tzdata)
    ZONA = timezone(timedelta(hours=-5), "America/Lima")  # Perú no usa horario de verano

DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
         "noviembre", "diciembre"]


def hoy_en_lima(ahora: datetime | None = None) -> date:
    """Fecha de hoy en Lima. `ahora` permite fijar el reloj en las pruebas."""
    ahora = ahora or datetime.now(timezone.utc)
    return ahora.astimezone(ZONA).date()


def fecha_en_texto(dia: date) -> str:
    """date(2026, 11, 10) -> 'martes 10 de noviembre de 2026'."""
    return f"{DIAS[dia.weekday()]} {dia.day} de {MESES[dia.month - 1]} de {dia.year}"


def _mes_siguiente(dia: date) -> int:
    return dia.month % 12 + 1


# Expresiones relativas en los idiomas del demo -> función que da el mes a partir de hoy.
# "mañana" no está: en español también es "la mañana" (parte del día).
_RELATIVAS = [
    (r"next week|(?:la )?pr[óo]xima semana|la semana que viene|semaine prochaine|n[äa]chste[n]? woche",
     lambda d: (d + timedelta(days=7)).month),
    (r"next month|(?:el )?pr[óo]ximo m[eê]s|el mes que viene|mois prochain|n[äa]chste[nr]? monat",
     _mes_siguiente),
    (r"this week|esta semana|cette semaine|diese[rn]? woche|this month|este m[eê]s|ce mois|diese[nr]? monat|"
     r"today|tomorrow|\bhoy\b|hoje|amanh[ãa]|aujourd'hui|demain|\bheute\b",
     lambda d: d.month),
]


def mes_relativo(texto: str | None, hoy: date) -> int | None:
    """Mes del viaje si el texto es una fecha relativa a hoy; None si no lo es."""
    if not texto:
        return None
    for patron, mes in _RELATIVAS:
        if re.search(patron, texto, flags=re.IGNORECASE):
            return mes(hoy)
    return None
