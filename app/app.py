"""Abra Travel: app web para responder consultas de viajeros.

Ejecutar en local:  streamlit run app/app.py
Luego abrir http://localhost:8501 en el navegador.

Diseño (colores, tipografía, orden de la pantalla): docs/diseno.md. El tema está en
.streamlit/config.toml y el CSS que el tema no cubre, en app/estilo.css.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import streamlit as st

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "app"))

from ai.ejemplo import AVISO_SIN_CUOTA, cargar_ejemplo, responder_con_respaldo  # noqa: E402
from ai.knowledge import BaseConocimiento  # noqa: E402
from ai.llm import ClaveInvalidaError, crear_llm  # noqa: E402
from ai.pipeline import AGENCIA  # noqa: E402
from core.cotizacion import cargar_extras, cargar_tarifario  # noqa: E402
from core.whatsapp import enlace_whatsapp  # noqa: E402
from presentacion import html_opciones, html_perfil, lista_markdown, separar_advertencias  # noqa: E402

try:  # .env en local (con la clave). En Streamlit Cloud se usan los secretos.
    from dotenv import load_dotenv

    load_dotenv(RAIZ / ".env")
except ImportError:
    pass

EJEMPLO = (
    "Hi! We are 2 friends planning to visit Cusco in late March. Is the Salkantay trek to Machu Picchu "
    "possible in 4 or 5 days? How much would it cost per person and what is included? Thanks!"
)
CLAVE_POR_PROVEEDOR = {"gemini": "GEMINI_API_KEY", "claude": "ANTHROPIC_API_KEY"}
COLUMNAS_TARIFARIO = [
    "trek_id", "ruta", "trek", "dias", "nivel", "precio_usd_pp_grupo_2", "precio_usd_pp_grupo_3a4",
    "precio_usd_pp_grupo_5mas", "tamano_max_grupo", "requiere_permiso_camino_inca", "meses_no_disponible",
    "incluye", "no_incluye",
]
LOGO = str(RAIZ / "assets" / "logo.svg")
ICONO = str(RAIZ / "assets" / "icono.svg")

st.set_page_config(page_title="Abra Travel", page_icon=ICONO, layout="wide")


@st.cache_data
def estilo() -> str:
    return (RAIZ / "app" / "estilo.css").read_text(encoding="utf-8")


# Se lee una vez (caché) y se aplica en cada recarga. st.html quita las etiquetas <style>; st.markdown no.
st.markdown(f"<style>{estilo()}</style>", unsafe_allow_html=True)


# ---------------------------------------------------------------- Configuración
def leer_secretos() -> None:
    """En Streamlit Cloud las claves vienen de st.secrets; se copian al entorno para ai/llm.py."""
    try:
        for nombre in ("LLM_PROVIDER", "GEMINI_API_KEY", "GEMINI_MODEL", "ANTHROPIC_API_KEY", "ANTHROPIC_MODEL"):
            if nombre in st.secrets and not os.getenv(nombre):
                os.environ[nombre] = str(st.secrets[nombre])
    except Exception:  # noqa: BLE001 - sin archivo de secretos en local
        pass


def proveedor() -> str:
    return (os.getenv("LLM_PROVIDER") or "gemini").strip().lower()


def falta_clave() -> str | None:
    """Nombre de la variable que falta, o None si la clave está."""
    variable = CLAVE_POR_PROVEEDOR.get(proveedor(), "GEMINI_API_KEY")
    return None if os.getenv(variable) else variable


@st.cache_resource
def base_conocimiento() -> BaseConocimiento:
    return BaseConocimiento(RAIZ / "data" / "knowledge")


@st.cache_resource
def modelo(nombre_proveedor: str):
    return crear_llm(nombre_proveedor)


leer_secretos()
if "tarifario" not in st.session_state:
    # tarifario_base es lo que muestra el editor; tarifario es el resultado editado, con el que se cotiza.
    st.session_state.tarifario_base = cargar_tarifario(RAIZ / "data" / "tarifario_demo.csv")
    st.session_state.tarifario = st.session_state.tarifario_base
if "extras" not in st.session_state:
    st.session_state.extras = cargar_extras(RAIZ / "data" / "extras_demo.csv")
if "agencia" not in st.session_state:
    st.session_state.agencia = AGENCIA

st.logo(LOGO, icon_image=ICONO, size="large")
st.sidebar.caption(f"Agencia: **{st.session_state.agencia}**")
pagina = st.sidebar.radio("Ir a", ["Nueva consulta", "Mi agencia"])
st.sidebar.divider()
st.sidebar.caption("Revisas cada respuesta antes de enviarla. Ningún mensaje se envía solo.")


def rotulo(texto: str) -> None:
    st.html(f'<p class="rotulo">{texto}</p>')


# ---------------------------------------------------------------- Nueva consulta
def usar_ejemplo() -> None:
    """Muestra el resultado guardado de una consulta real, sin llamar a la API (no gasta cuota)."""
    try:
        resultado, datos = cargar_ejemplo()
    except (OSError, ValueError, KeyError):  # sin ejemplo guardado: solo se pega el mensaje
        st.session_state.consulta = EJEMPLO
        return
    st.session_state.consulta = datos["consulta"]
    st.session_state.resultado = resultado
    st.session_state.borrador = resultado.borrador.mensaje_para_cliente
    st.session_state.origen = "ejemplo"
    st.session_state.fecha_ejemplo = datos.get("fecha", "")


def mostrar_borrador(resultado, telefono: str) -> None:
    """(1) Lo que se envía: el borrador editable y el botón de WhatsApp."""
    with st.container(border=True, key="tarjeta_borrador"):
        rotulo("Respuesta lista para enviar")
        texto = st.text_area("Revisa el mensaje y edítalo si hace falta", key="borrador", height=230)
        st.caption(f"{len(texto.split())} palabras · se envía desde tu WhatsApp, nada sale solo")
        # Justo encima del botón, para que se vea sin bajar.
        st.caption(f"Respondió: {resultado.uso.modelos_que_respondieron()} · Tokens usados: "
                   f"{resultado.uso.tokens_entrada} de entrada y {resultado.uso.tokens_salida} de salida "
                   f"(2 llamadas al modelo).")
        st.link_button("Abrir en WhatsApp", enlace_whatsapp(texto, telefono), type="primary",
                       icon=":material/send:", disabled=not texto.strip(), width="stretch")


def mostrar_avisos(resultado) -> None:
    """(2) Avisos del control, agrupados: lo grave en rojo y arriba."""
    graves, revisar = separar_advertencias(resultado.advertencias)
    if graves:
        st.error("**Corrige antes de enviar**\n\n" + lista_markdown(graves), icon=":material/error:")
    if revisar:
        st.warning("**Revisa antes de enviar**\n\n" + lista_markdown(revisar), icon=":material/visibility:")
    if not graves and not revisar:
        st.success("El control no encontró problemas. Igual lee el mensaje antes de enviarlo.",
                   icon=":material/check_circle:")


def mostrar_opciones(resultado) -> None:
    """(3) Opciones del tarifario como filas comparables."""
    rotulo("Opciones de tu tarifario")
    if not resultado.opciones:
        st.warning("Ninguna fila de tu tarifario encaja con esta consulta.")
    else:
        st.html(html_opciones(resultado.opciones))
    if resultado.aviso:  # el aviso más importante para el viajero: visible, no en letra chica
        st.info(f"**Aviso para el viajero:** {resultado.aviso}", icon=":material/info:")
    with st.expander("Información consultada (con fecha)"):
        for f in resultado.fragmentos:
            st.markdown(f"**{f.titulo}** · `{f.archivo}` · actualizado {f.actualizado}")


def mostrar_perfil(perfil) -> None:
    """(4) Perfil del viajero en fichas compactas; lo que falta, como etiquetas."""
    with st.container(border=True, key="tarjeta_perfil"):
        rotulo("Lo que entendimos del viajero")
        st.html(html_perfil(perfil))


def pagina_consulta() -> None:
    st.header("Nueva consulta")
    st.html('<p class="subtitulo">Pega el mensaje del viajero y recibe una respuesta en su idioma, '
            'con precios de tu tarifario, lista para WhatsApp.</p>')

    variable = falta_clave()
    if variable:
        st.warning(
            f"Falta la clave **{variable}** para el proveedor **{proveedor()}**. "
            "Cópiala en el archivo `.env` de la carpeta del proyecto (ver `.env.example`) y vuelve a abrir la app. "
            "Mientras tanto puedes ver un resultado guardado con **Usar mensaje de ejemplo** o revisar tu "
            "tarifario en **Mi agencia**.", icon=":material/key_off:")

    resultado = st.session_state.get("resultado")
    with st.container(border=True, key="tarjeta_entrada"):
        consulta = st.text_area("Mensaje del viajero", key="consulta", height=96 if resultado else 140,
                                placeholder=EJEMPLO)
        telefono = st.text_input("WhatsApp del viajero (opcional, con código de país)",
                                 placeholder="+1 555 123 4567")
        with st.container(horizontal=True, vertical_alignment="center"):
            preparar = st.button("Preparar respuesta", type="primary", icon=":material/edit_note:",
                                 disabled=not consulta or bool(variable))
            st.button("Usar mensaje de ejemplo", type="tertiary", on_click=usar_ejemplo,
                      help="Muestra una consulta real ya resuelta. No gasta cuota del modelo.")

    if preparar:
        try:
            with st.spinner("Leyendo el mensaje, cotizando con tu tarifario y redactando la respuesta…"):
                # Cadena de respaldo: modelo principal -> modelo de respaldo -> ejemplo guardado.
                resultado, es_ejemplo = responder_con_respaldo(
                    consulta, modelo(proveedor()), base_conocimiento(), st.session_state.tarifario,
                    st.session_state.extras, st.session_state.agencia)
        except ClaveInvalidaError as error:  # esperar no sirve: hay que cambiar la clave
            st.error(str(error), icon=":material/key_off:")
            return
        except Exception as error:  # noqa: BLE001 - se muestra un mensaje claro en vez del error técnico
            st.error("No se pudo preparar la respuesta. Intenta de nuevo en un minuto.", icon=":material/error:")
            with st.expander("Detalle técnico"):
                st.code(f"{type(error).__name__}: {error}")
            return
        st.session_state.resultado = resultado
        st.session_state.borrador = resultado.borrador.mensaje_para_cliente
        st.session_state.origen = "sin_cuota" if es_ejemplo else "modelo"

    resultado = st.session_state.get("resultado")
    if not resultado:
        st.html('<div class="vacio"><strong>Aquí aparecerá la respuesta.</strong> Abra Travel entiende qué pide '
                'el viajero, elige opciones de tu tarifario y redacta el mensaje. Tú lo revisas y lo envías '
                'por WhatsApp.</div>')
        return

    origen = st.session_state.get("origen", "modelo")
    if origen == "sin_cuota":
        st.warning(f"**{AVISO_SIN_CUOTA}.** Este resultado no corresponde al mensaje que pegaste; "
                   "vuelve a intentarlo mañana.", icon=":material/hourglass_empty:")
    elif origen == "ejemplo":
        st.info(f"Resultado guardado de una consulta real al modelo ({st.session_state.get('fecha_ejemplo', '')}). "
                "No se llamó a la API, así que no gastó cuota.", icon=":material/bookmark:")

    # Laptop: borrador y opciones lado a lado. Celular: una columna, el borrador primero.
    izquierda, derecha = st.columns([7, 5], gap="large")
    with izquierda:
        mostrar_borrador(resultado, telefono)
    with derecha:
        mostrar_avisos(resultado)
        mostrar_opciones(resultado)
    mostrar_perfil(resultado.perfil)


# ---------------------------------------------------------------- Mi agencia
COLUMNAS_LEGIBLES = {
    "trek_id": st.column_config.TextColumn("Código"),
    "ruta": st.column_config.TextColumn("Ruta"),
    "trek": st.column_config.TextColumn("Trek", width="medium"),
    "dias": st.column_config.NumberColumn("Días", format="%d"),
    "nivel": st.column_config.TextColumn("Nivel"),
    "precio_usd_pp_grupo_2": st.column_config.NumberColumn("US$ por persona (1–2)", format="%d"),
    "precio_usd_pp_grupo_3a4": st.column_config.NumberColumn("US$ por persona (3–4)", format="%d"),
    "precio_usd_pp_grupo_5mas": st.column_config.NumberColumn("US$ por persona (5+)", format="%d"),
    "tamano_max_grupo": st.column_config.NumberColumn("Grupo máximo", format="%d"),
    "requiere_permiso_camino_inca": st.column_config.TextColumn("Permiso Camino Inca"),
    "meses_no_disponible": st.column_config.TextColumn("Meses cerrado"),
    "incluye": st.column_config.TextColumn("Incluye", width="large"),
    "no_incluye": st.column_config.TextColumn("No incluye", width="large"),
    "llega_a_machu_picchu": st.column_config.TextColumn("Llega a Machu Picchu"),
    "origen_precio": st.column_config.TextColumn("De dónde sale el precio", width="large"),
}


def pagina_agencia() -> None:
    st.header("Mi agencia")
    st.html('<p class="subtitulo">Tu tarifario. Abra Travel solo cotiza con estos precios: '
            'el modelo nunca los inventa.</p>')
    st.session_state.agencia = st.text_input("Nombre de la agencia", st.session_state.agencia)

    with st.container(border=True, key="tarjeta_tarifario"):
        rotulo("Tarifario")
        st.caption("Edita una celda para cambiar un precio, o sube tu tarifario en CSV con las mismas columnas.")
        subido = st.file_uploader("Subir mi tarifario (CSV)", type="csv", max_upload_size=5)
        if subido is not None and st.session_state.get("ultimo_csv") != subido.file_id:  # solo si es un archivo nuevo
            st.session_state.ultimo_csv = subido.file_id
            try:
                nuevo = cargar_tarifario(subido)
            except Exception as error:  # noqa: BLE001
                st.error(f"No se pudo leer el CSV: {error}")
            else:
                faltan = [c for c in COLUMNAS_TARIFARIO if c not in nuevo.columns]
                if faltan:
                    st.error("Al CSV le faltan estas columnas: " + ", ".join(faltan))
                else:
                    st.session_state.tarifario_base = nuevo
                    st.session_state.tarifario = nuevo
                    st.session_state.pop("editor_tarifario", None)  # el editor empieza de cero con el CSV nuevo
                    st.success(f"Tarifario cargado: {len(nuevo)} filas.")

        st.session_state.tarifario = st.data_editor(st.session_state.tarifario_base, num_rows="dynamic",
                                                    width="stretch", key="editor_tarifario",
                                                    column_config=COLUMNAS_LEGIBLES, hide_index=True)
        with st.container(horizontal=True, vertical_alignment="center"):
            st.download_button("Descargar tarifario", st.session_state.tarifario.to_csv(index=False).encode("utf-8"),
                               file_name="tarifario.csv", mime="text/csv", icon=":material/download:")
            st.caption("Los cambios valen mientras la app esté abierta. Descarga el CSV para guardarlos.")


{"Nueva consulta": pagina_consulta, "Mi agencia": pagina_agencia}[pagina]()
