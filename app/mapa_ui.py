"""Mapa de la ruta de un trek en Streamlit. Todo va dentro de un try/except: si algo falla, la app sigue."""
from __future__ import annotations

from core import mapa

SIN_MAPA = "Mapa no disponible todavía para este trek."
AVISO_ERROR = "No se pudo mostrar el mapa en este momento. El resto de la respuesta no se ve afectado."

COLOR_TIPO = {  # mismos tonos de docs/diseno.md
    "inicio": [30, 107, 82], "fin": [21, 48, 43], "campamento": [201, 116, 29],
    "paso": [180, 71, 31], "sitio": [91, 111, 106],
}
ETIQUETA_TIPO = {"inicio": "Inicio", "fin": "Fin", "campamento": "Campamento", "paso": "Paso", "sitio": "Lugar"}


def _dibujar(st, ruta: mapa.Ruta) -> None:
    import pandas as pd
    import pydeck as pdk

    datos = pd.DataFrame([{
        "lugar": p.lugar, "tipo": ETIQUETA_TIPO.get(p.tipo, "Lugar"), "dia": p.dia,
        "altitud": f"{p.altitud_m:,} m".replace(",", " ") if p.altitud_m else "sin dato",
        "lon": p.longitud, "lat": p.latitud, "color": COLOR_TIPO.get(p.tipo, COLOR_TIPO["sitio"]),
        "radio": 380 if p.tipo in ("inicio", "fin", "campamento", "paso") else 240,
    } for p in ruta.puntos])
    camino = pd.DataFrame([{"camino": [[p.longitud, p.latitud] for p in ruta.puntos]}])
    capas = [
        pdk.Layer("PathLayer", camino, get_path="camino", get_color=[30, 107, 82, 160], width_min_pixels=3),
        pdk.Layer("ScatterplotLayer", datos, get_position=["lon", "lat"], get_fill_color="color",
                  get_radius="radio", radius_min_pixels=5, radius_max_pixels=11, pickable=True),
    ]
    vista = pdk.ViewState(latitude=float(datos["lat"].mean()), longitude=float(datos["lon"].mean()),
                          zoom=9.2 if len(ruta.puntos) > 2 else 11)
    tooltip = {"text": "{lugar}\n{tipo} · día {dia}\nAltitud: {altitud}"}
    st.pydeck_chart(pdk.Deck(layers=capas, initial_view_state=vista, tooltip=tooltip), height=420)


def mostrar_mapa(trek: str | None) -> None:
    """Dibuja la ruta del trek (id de ruta: 'salkantay', 'camino_inca', 'lares'). Nunca lanza excepciones."""
    try:
        import streamlit as st

        ruta = mapa.cargar_ruta(trek)
        if ruta is None:
            st.info(SIN_MAPA, icon=":material/map:")
            st.caption(mapa.ATRIBUCION)
            return
        _dibujar(st, ruta)
        dias = mapa.archivo_dias(ruta.archivo)
        st.caption(f"Puntos clave de un itinerario de referencia de {dias} días; las rutas varían entre agencias. "
                   f"{mapa.ATRIBUCION}")
        claves = [f"{ETIQUETA_TIPO.get(p.tipo, 'Lugar')}: {p.lugar}" for p in ruta.de_tipo("inicio", "campamento", "fin")]
        if claves:
            st.markdown("**Inicio, campamentos y fin:** " + " · ".join(claves))
        if ruta.ruta == "lares":
            st.warning("Los datos de Lares están incompletos: faltan los campamentos y el tramo alto de los días 1 y 2.",
                       icon=":material/info:")
    except Exception:  # noqa: BLE001 - el mapa nunca debe tumbar la app
        try:
            import streamlit as st
            st.warning(AVISO_ERROR, icon=":material/info:")
        except Exception:  # noqa: BLE001
            pass


def trek_detectado(resultado) -> str | None:
    """Primer trek que pidió el viajero (id de ruta), o None si no se detectó ninguno."""
    try:
        treks = list(resultado.perfil.treks_de_interes or [])
        return str(treks[0]) if treks else None
    except Exception:  # noqa: BLE001
        return None


def mostrar_mapa_del_resultado(resultado) -> None:
    """Expander "Ver la ruta en el mapa" con el trek detectado; no muestra nada si no hay trek."""
    try:
        import streamlit as st

        trek = trek_detectado(resultado)
        if not trek:
            return
        with st.expander("Ver la ruta en el mapa", icon=":material/map:"):
            mostrar_mapa(trek)
    except Exception:  # noqa: BLE001
        pass
