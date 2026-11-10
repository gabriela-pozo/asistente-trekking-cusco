"""Enlace "click to chat" de WhatsApp: abre el chat con el mensaje ya escrito.

https://wa.me/<número>?text=<mensaje codificado>

- No usa la API de WhatsApp Business: no necesita cuenta de Meta, aprobación ni plantillas,
  y no tiene costo por mensaje.
- No envía nada: abre WhatsApp (app o web) con el texto puesto, y el vendedor presiona enviar.
- El número va solo con dígitos y con código de país (51 para Perú, 1 para EE. UU.).
  Sin número, WhatsApp pide elegir el contacto.
"""
from __future__ import annotations

import re
from urllib.parse import quote


def solo_digitos(telefono: str | None) -> str:
    """'+1 (555) 123-4567' -> '15551234567'."""
    return re.sub(r"\D", "", telefono or "")


def enlace_whatsapp(texto: str, telefono: str | None = None) -> str:
    """Enlace wa.me con el mensaje codificado para URL (espacios, saltos de línea, tildes, US$)."""
    digitos = solo_digitos(telefono)
    base = f"https://wa.me/{digitos}" if digitos else "https://wa.me/"
    return f"{base}?text={quote(texto, safe='')}"
