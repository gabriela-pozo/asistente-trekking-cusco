"""Recarga de ai/ y core/ cuando cambian, sin reiniciar el servidor.

Cuando el código cambia (por ejemplo, Streamlit Cloud baja un commit nuevo), Streamlit vuelve a correr
app.py pero solo recarga los módulos de la carpeta del script (app/). Los de ai/ y core/ quedan en
memoria con la versión vieja: así se cayó el demo el 2026-11-10 ("ImportError: from ai.pipeline import
AGENCIA, aplicar_paquete", porque el ai.pipeline en memoria era anterior a aplicar_paquete).

recargar_si_cambiaron() se llama al principio de app.py: si algún archivo de ai/ o core/ cambió desde que
se cargó, saca de sys.modules todos los módulos de esos paquetes (todos juntos, para no mezclar versiones),
y el import siguiente los vuelve a leer del disco. marcar_cargados() se llama después de los imports.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

PAQUETES = ("ai", "core")
_MARCA = "__abra_mtime__"


def _modulos_del_proyecto(raiz: Path) -> dict[str, tuple[object, str]]:
    salida = {}
    for nombre, modulo in list(sys.modules.items()):
        archivo = getattr(modulo, "__file__", None)
        if nombre.split(".")[0] in PAQUETES and archivo and Path(archivo).resolve().is_relative_to(raiz):
            salida[nombre] = (modulo, archivo)
    return salida


def _mtime(archivo: str) -> float | None:
    try:
        return os.path.getmtime(archivo)
    except OSError:
        return None


def marcar_cargados(raiz: Path) -> None:
    """Anota la fecha del archivo de cada módulo recién cargado."""
    for modulo, archivo in _modulos_del_proyecto(raiz).values():
        if getattr(modulo, _MARCA, None) is None:
            setattr(modulo, _MARCA, _mtime(archivo))


def recargar_si_cambiaron(raiz: Path) -> list[str]:
    """Si algún módulo de ai/ o core/ cambió en el disco, los saca a todos de sys.modules. Devuelve cuáles."""
    modulos = _modulos_del_proyecto(raiz)
    cambio = any(getattr(m, _MARCA, None) not in (None, _mtime(a)) for m, a in modulos.values())
    if not cambio:
        return []
    for nombre in modulos:
        sys.modules.pop(nombre, None)
    return sorted(modulos)
