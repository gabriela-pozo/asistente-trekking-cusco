"""Mapa de la ruta de un trek en Streamlit. Todo va dentro de un try/except: si algo falla, la app sigue."""
from __future__ import annotations

from core import mapa

SIN_MAPA = "Mapa no disponible todavía para este trek."
AVISO_ERROR = "No se pudo mostrar el mapa en este momento. El resto de la respuesta no se ve afectado."

COLOR_TIPO = {  # mismos tonos de docs/diseno.md
    "inicio": [11, 110, 127], "fin": [18, 48, 58], "campamento": [200, 102, 10],
    "paso": [180, 95, 6], "sitio": [92, 110, 116],
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
        pdk.Layer("PathLayer", camino, get_path="camino", get_color=[11, 110, 127, 160], width_min_pixels=3),
        pdk.Layer("ScatterplotLayer", datos, get_position=["lon", "lat"], get_fill_color="color",
                  get_radius="radio", radius_min_pixels=5, radius_max_pixels=11, pickable=True),
    ]
    vista = pdk.ViewState(latitude=float(datos["lat"].mean()), longitude=float(datos["lon"].mean()),
                          zoom=9.2 if len(ruta.puntos) > 2 else 11)
    tooltip = {"text": "{lugar}\n{tipo} · día {dia}\nAltitud: {altitud}"}
    st.pydeck_chart(pdk.Deck(layers=capas, initial_view_state=vista, tooltip=tooltip), height=420)


def _perfil(st, ruta: mapa.Ruta) -> None:
    """Perfil de altitud con los puntos que tienen altitud; no dibuja nada si hay menos de 3."""
    perfil = mapa.perfil_altitud(ruta)
    if not perfil:
        return
    import altair as alt
    import pandas as pd

    datos = pd.DataFrame(perfil, columns=["Lugar", "Km en línea recta", "Altitud (m)"])
    base = alt.Chart(datos).encode(
        x=alt.X("Km en línea recta:Q", title="Km acumulados en línea recta"),
        y=alt.Y("Altitud (m):Q", title="Altitud (m)", scale=alt.Scale(zero=False)),
        tooltip=["Lugar", alt.Tooltip("Altitud (m):Q", format=",.0f")])
    grafico = (base.mark_line(color="#0B6E7F") + base.mark_circle(color="#C8660A", size=70)).properties(height=220)
    st.markdown("**Perfil de altitud**")
    st.altair_chart(grafico)
    d = mapa.desnivel(ruta)
    if d:
        miles = lambda n: f"{n:,}".replace(",", " ")  # noqa: E731
        st.caption(f"Altitud entre {miles(d['minima_m'])} y {miles(d['maxima_m'])} m, calculada con "
                   f"{d['puntos_con_altitud']} de {d['puntos']} puntos (los demás no tienen altitud en las fuentes).")


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
        _perfil(st, ruta)
        url = mapa.enlace_google_maps(ruta)
        if url:
            st.link_button("Abrir punto de inicio en Google Maps", url, icon=":material/open_in_new:")
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
