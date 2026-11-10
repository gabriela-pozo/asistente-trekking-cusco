"""Abra Travel: app web para responder consultas de viajeros.

Ejecutar en local:  streamlit run app/app.py
Luego abrir http://localhost:8501 en el navegador.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from ai.ejemplo import AVISO_SIN_CUOTA, cargar_ejemplo, responder_con_respaldo  # noqa: E402
from ai.knowledge import BaseConocimiento  # noqa: E402
from ai.llm import ClaveInvalidaError, crear_llm  # noqa: E402
from ai.pipeline import AGENCIA  # noqa: E402
from core.cotizacion import NOMBRE_NIVEL, cargar_extras, cargar_tarifario  # noqa: E402
from core.whatsapp import enlace_whatsapp  # noqa: E402

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

st.set_page_config(page_title="Abra Travel", page_icon="🏔️", layout="wide")


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

st.sidebar.title("🏔️ Abra Travel")
st.sidebar.caption(f"Agencia: {st.session_state.agencia}")
pagina = st.sidebar.radio("Ir a", ["Nueva consulta", "Mi agencia"])
st.sidebar.divider()
st.sidebar.caption("Revisas cada respuesta antes de enviarla. Ningún mensaje se envía solo.")


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


def mostrar_perfil(perfil) -> None:
    st.subheader("Perfil del viajero")
    datos = {
        "Idioma": perfil.idioma,
        "Personas": perfil.num_personas,
        "Mes del viaje": perfil.mes_viaje,
        "Fechas": perfil.fecha_texto,
        "Días disponibles": perfil.dias_disponibles,
        "Treks de interés": ", ".join(perfil.treks_de_interes),
        "Nivel": NOMBRE_NIVEL.get(perfil.nivel_preferido or "", ""),
        "Presupuesto (US$ por persona)": perfil.presupuesto_usd_pp,
        "Extras": ", ".join(perfil.extras_de_interes),
    }
    tabla = pd.DataFrame({"Dato": list(datos), "Valor": [str(v) if v not in (None, "") else "—" for v in datos.values()]})
    st.dataframe(tabla, hide_index=True, width="stretch")
    if perfil.datos_faltantes:
        st.info("Faltan: " + ", ".join(perfil.datos_faltantes))


def mostrar_opciones(resultado) -> None:
    st.subheader("Opciones de tu tarifario")
    if not resultado.opciones:
        st.warning("Ninguna fila de tu tarifario encaja con esta consulta.")
    else:
        st.dataframe(pd.DataFrame([
            {
                "Trek": o.trek, "Días": o.dias, "Nivel": NOMBRE_NIVEL.get(o.nivel, o.nivel),
                "US$ por persona": o.precio_pp_con_extras, "Personas": o.personas, "Total US$": o.total,
                "Depósito US$": o.deposito, "Alternativa": "Sí" if o.es_alternativa else "No",
            }
            for o in resultado.opciones
        ]), hide_index=True, width="stretch")
    if resultado.aviso:
        st.caption(f"Aviso clave: {resultado.aviso}")
    with st.expander("Información consultada (con fecha)"):
        for f in resultado.fragmentos:
            st.markdown(f"**{f.titulo}** · `{f.archivo}` · actualizado {f.actualizado}")


def pagina_consulta() -> None:
    st.header("Nueva consulta")
    st.write("Pega el mensaje del viajero. Abra Travel arma su perfil, elige opciones de tu tarifario y "
             "redacta la respuesta en su idioma.")

    variable = falta_clave()
    if variable:
        st.warning(
            f"Falta la clave **{variable}** para el proveedor **{proveedor()}**. "
            "Cópiala en el archivo `.env` de la carpeta del proyecto (ver `.env.example`) y vuelve a abrir la app. "
            "Mientras tanto puedes revisar tu tarifario en **Mi agencia**."
        )

    st.button("Usar mensaje de ejemplo", on_click=usar_ejemplo)
    consulta = st.text_area("Mensaje del viajero", key="consulta", height=140, placeholder=EJEMPLO)
    telefono = st.text_input("WhatsApp del viajero (opcional, con código de país)", placeholder="+1 555 123 4567")

    if st.button("Preparar respuesta", type="primary", disabled=not consulta or bool(variable)):
        try:
            with st.spinner("Leyendo la consulta y armando la cotización..."):
                # Cadena de respaldo: modelo principal -> modelo de respaldo -> ejemplo guardado.
                resultado, es_ejemplo = responder_con_respaldo(
                    consulta, modelo(proveedor()), base_conocimiento(), st.session_state.tarifario,
                    st.session_state.extras, st.session_state.agencia)
        except ClaveInvalidaError as error:  # esperar no sirve: hay que cambiar la clave
            st.error(str(error))
            return
        except Exception as error:  # noqa: BLE001 - se muestra un mensaje claro en vez del error técnico
            st.error("No se pudo preparar la respuesta. Intenta de nuevo en un minuto.")
            with st.expander("Detalle técnico"):
                st.code(f"{type(error).__name__}: {error}")
            return
        st.session_state.resultado = resultado
        st.session_state.borrador = resultado.borrador.mensaje_para_cliente
        st.session_state.origen = "sin_cuota" if es_ejemplo else "modelo"

    resultado = st.session_state.get("resultado")
    if not resultado:
        return

    origen = st.session_state.get("origen", "modelo")
    if origen == "sin_cuota":
        st.warning(f"**{AVISO_SIN_CUOTA}.** Este resultado no corresponde al mensaje que pegaste; "
                   "vuelve a intentarlo mañana.")
    elif origen == "ejemplo":
        st.info(f"Resultado guardado de una consulta real al modelo ({st.session_state.get('fecha_ejemplo', '')}). "
                "No se llamó a la API, así que no gastó cuota.")

    col1, col2 = st.columns([1, 2])
    with col1:
        mostrar_perfil(resultado.perfil)
    with col2:
        mostrar_opciones(resultado)

    st.subheader("Respuesta para el viajero")
    if resultado.advertencias:
        st.markdown("**Revisa antes de enviar:**")
        for advertencia in resultado.advertencias:
            st.warning(advertencia)
    else:
        st.success("El control no encontró problemas. Igual revisa el mensaje antes de enviarlo.")
    texto = st.text_area("Edita el mensaje si hace falta", key="borrador", height=260)
    st.caption(f"{len(texto.split())} palabras")
    # Justo encima del botón, para que se vea sin bajar.
    st.caption(f"Respondió: {resultado.uso.modelos_que_respondieron()} · Tokens usados: "
               f"{resultado.uso.tokens_entrada} de entrada y {resultado.uso.tokens_salida} de salida "
               f"(2 llamadas al modelo).")
    st.link_button("Abrir en WhatsApp", enlace_whatsapp(texto, telefono), type="primary", disabled=not texto.strip())


# ---------------------------------------------------------------- Mi agencia
def pagina_agencia() -> None:
    st.header("Mi agencia")
    st.session_state.agencia = st.text_input("Nombre de la agencia", st.session_state.agencia)
    st.write("Este es tu tarifario. Abra Travel solo cotiza con estos precios: el modelo nunca los inventa. "
             "Puedes editarlo aquí o subir el tuyo en CSV con las mismas columnas.")

    subido = st.file_uploader("Subir tarifario (CSV)", type="csv")
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
                                                width="stretch", key="editor_tarifario")
    st.download_button("Descargar tarifario en CSV", st.session_state.tarifario.to_csv(index=False).encode("utf-8"),
                       file_name="tarifario.csv", mime="text/csv")
    st.caption("Los cambios valen mientras la app esté abierta. Descarga el CSV para guardarlos.")


{"Nueva consulta": pagina_consulta, "Mi agencia": pagina_agencia}[pagina]()
