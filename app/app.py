"""Abra Travel: app web para responder consultas de viajeros.

Ejecutar en local:  streamlit run app/app.py
Luego abrir http://localhost:8501 en el navegador.

Diseño (colores, tipografía, orden de la pantalla): docs/diseno.md. El tema está en
.streamlit/config.toml y el CSS que el tema no cubre, en app/estilo.css.
"""
from __future__ import annotations

import html
import os
import sys
from datetime import datetime
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "app"))

from recarga import marcar_cargados, recargar_si_cambiaron  # noqa: E402

# Streamlit solo recarga los módulos de app/: si ai/ o core/ cambiaron (un commit nuevo en Streamlit Cloud),
# se vuelven a leer del disco. Sin esto, el demo se cayó con un ImportError de ai.pipeline (ver app/recarga.py).
recargar_si_cambiaron(RAIZ)

from ai.ejemplo import AVISO_SIN_CUOTA, cargar_ejemplo, responder_con_respaldo  # noqa: E402
from ai.fecha import ZONA, hoy_en_lima  # noqa: E402
from ai.knowledge import BaseConocimiento  # noqa: E402
from ai.llm import ClaveInvalidaError, crear_llm  # noqa: E402
from ai.pipeline import AGENCIA, aplicar_paquete  # noqa: E402
from ai.trazabilidad import (  # noqa: E402
    DIAS_PARA_VERIFICAR, ETIQUETA_VERIFICAR, buscar_en_base, consultas_restantes, contar_pruebas, dominio,
    es_oficial, fuentes_usadas, modelos_configurados, referencia_cuota, tabla_base, version_base,
)
from core.cotizacion import NOMBRE_NIVEL, NOMBRE_RUTA, cargar_extras, cargar_tarifario  # noqa: E402
from core.mi_semana import (  # noqa: E402
    META_POR_DEFECTO, cambiar_estado, inicio_semana, leer_registradas, pendientes, progreso_meta, racha, semana,
)
from core.paquete import (  # noqa: E402
    METODOS, RECARGOS, UNIDADES, Seleccion, armar_paquete, extras_aplicables, fila_del_trek, noches_sugeridas,
    sugeridos_validos,
)
from core.respuesta_nocturna import (  # noqa: E402
    APERTURA, CIERRE, advertencias_de_control, fuera_de_horario, respuesta_nocturna,
)
from core.tablero import (  # noqa: E402
    cargar_consultas, contar_registradas, filtrar, metricas, por_mes_viaje, por_pais, por_trek, registrar,
    registro_desde_resultado,
)
from core.whatsapp import enlace_whatsapp  # noqa: E402
from presentacion import (  # noqa: E402
    html_desglose, html_opciones, html_perfil, idioma, lista_markdown, separar_advertencias, usd,
)

marcar_cargados(RAIZ)

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
CONSULTAS_SINTETICAS = RAIZ / "data" / "consultas_sinteticas.csv"
# Consultas registradas desde la app (solo el perfil agregado). No se sube al repositorio (.gitignore).
RUTA_REGISTRO = Path(os.getenv("ABRA_REGISTRO") or RAIZ / "data" / "consultas_registradas.csv")
ETIQUETA_SINTETICOS = "Datos sintéticos del demo: no son de ninguna agencia real"
ETIQUETA_SIMULACION = "Simulación: el envío automático requiere la API de WhatsApp Business (siguiente paso)"

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
if "extras" not in st.session_state:  # como el tarifario: extras_base para el editor, extras para cotizar
    st.session_state.extras_base = cargar_extras(RAIZ / "data" / "extras_demo.csv")
    st.session_state.extras = st.session_state.extras_base
st.session_state.setdefault("recargos", dict(RECARGOS))  # % por forma de pago, editable en "Mi agencia"
if "agencia" not in st.session_state:
    st.session_state.agencia = AGENCIA
st.session_state.setdefault("apertura", APERTURA)  # horario de atención, en hora de Lima
st.session_state.setdefault("cierre", CIERRE)
st.session_state.setdefault("modo_nocturno", True)
st.session_state.setdefault("meta_semanal", META_POR_DEFECTO)  # consultas respondidas por semana ("Mi semana")
if "hora_llegada" not in st.session_state:  # por defecto, la hora actual en Lima
    st.session_state.hora_llegada = datetime.now(ZONA).time().replace(second=0, microsecond=0)

st.logo(LOGO, icon_image=ICONO, size="large")
st.sidebar.caption(f"Agencia: **{st.session_state.agencia}**")
pagina = st.sidebar.radio("Ir a", ["Nueva consulta", "Tablero", "Fuentes y verificación", "Mi agencia",
                                  "Estado del sistema"], key="pagina")
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
    st.session_state.registrada = None
    iniciar_paquete()


# ---------------------------------------------------------------- Paquete
# La selección del vendedor vive en st.session_state.seleccion; los widgets ("w_…") se rellenan desde ahí,
# porque Streamlit borra el estado de un widget cuando se cambia de página.
def seleccion_sugerida(resultado) -> Seleccion:
    """Lo que propone Abra Travel: los extras que sugirió el modelo (máx. 3) y 1 noche en Cusco si hace falta."""
    if not resultado.opciones:
        return Seleccion()
    fila = fila_del_trek(resultado.opciones[0], st.session_state.tarifario)
    sugeridos = sugeridos_validos(resultado.perfil.extras_sugeridos, st.session_state.extras, fila)
    return Seleccion(extras=[s.extra_id for s in sugeridos], noches_cusco=noches_sugeridas(resultado.perfil))


def componer_paquete() -> None:
    """Calcula el paquete con la selección actual y vuelve a armar el borrador (y sus controles)."""
    resultado = st.session_state.resultado
    paquete = armar_paquete(resultado.opciones, st.session_state.tarifario, st.session_state.extras,
                            st.session_state.seleccion, st.session_state.recargos)
    resultado = aplicar_paquete(resultado, paquete)
    st.session_state.resultado = resultado
    st.session_state.borrador = resultado.borrador.mensaje_para_cliente


def iniciar_paquete() -> None:
    """Con cada consulta nueva: selección sugerida y widgets en blanco."""
    for clave in [k for k in st.session_state if str(k).startswith("w_")]:
        del st.session_state[clave]
    st.session_state.seleccion = seleccion_sugerida(st.session_state.resultado)
    componer_paquete()


# Los widgets usan las etiquetas como opciones (y no format_func): así también funcionan en las pruebas (AppTest).
NOCHES = ["Ninguna", "1 noche", "2 noches"]
HOTELES = {3: "3★", 4: "4★"}


def etiquetas_base(opciones) -> list[str]:
    return [f"{o.trek}, {o.dias} días, {NOMBRE_NIVEL.get(o.nivel, o.nivel)} · {usd(o.precio_pp)} por persona"
            for o in opciones]


def etiquetas_pago() -> dict[str, str]:
    recargos = st.session_state.recargos
    return {m: nombre + (f" (+{recargos[m]:g} %)" if recargos.get(m) else "") for m, nombre in METODOS.items()}


def cambiar_paquete() -> None:
    """Callback de los widgets del paquete: lee lo que marcó el vendedor y vuelve a armar el borrador."""
    estado = st.session_state
    pagos = {v: k for k, v in etiquetas_pago().items()}
    estado.seleccion = Seleccion(
        base=etiquetas_base(estado.resultado.opciones).index(estado.w_base),
        noches_cusco=NOCHES.index(estado.w_noches),
        estrellas={v: k for k, v in HOTELES.items()}[estado.w_estrellas],
        metodo_pago=pagos.get(estado.w_metodo, "transferencia"),
        extras=[str(i) for i in estado.extras["extra_id"] if estado.get(f"w_extra_{i}")],
    )
    componer_paquete()


def mostrar_paquete(resultado) -> None:
    """(2b) Armar paquete: trek base + extras + días en Cusco + forma de pago, con el desglose."""
    if not resultado.opciones or resultado.paquete is None:
        return
    estado, sel = st.session_state, st.session_state.seleccion
    base = min(sel.base, len(resultado.opciones) - 1)
    aplicables = extras_aplicables(estado.extras, fila_del_trek(resultado.opciones[base], estado.tarifario))
    bases, pagos = etiquetas_base(resultado.opciones), etiquetas_pago()
    valores = {"w_base": bases[base], "w_noches": NOCHES[sel.noches_cusco], "w_estrellas": HOTELES[sel.estrellas],
               "w_metodo": pagos.get(sel.metodo_pago, pagos["transferencia"])}
    valores |= {f"w_extra_{i}": i in sel.extras for i in aplicables["extra_id"]}
    for clave, valor in valores.items():
        if clave not in estado or (clave == "w_metodo" and estado[clave] not in pagos.values()):
            estado[clave] = valor
    sugeridos = {s.extra_id: s for s in resultado.perfil.extras_sugeridos}

    with st.container(border=True, key="tarjeta_paquete"):
        rotulo("Armar paquete")
        st.selectbox("Trek base", bases, key="w_base", on_change=cambiar_paquete)
        st.markdown("**Extras opcionales**")
        for _, e in aplicables.iterrows():
            i = str(e["extra_id"])
            st.checkbox(f"{e['extra']} · {usd(e['precio_usd'])} {e['unidad']}", key=f"w_extra_{i}",
                        on_change=cambiar_paquete, help=f"Precio: {e.get('origen_precio', '')}")
            if i in sugeridos:
                st.caption(f":material/auto_awesome: Sugerido por lo que escribió: {sugeridos[i].motivo}")
        st.markdown("**Días en Cusco antes del trek**")
        with st.container(horizontal=True):
            st.radio("Noches", NOCHES, key="w_noches", on_change=cambiar_paquete, horizontal=True)
            st.radio("Hotel", list(HOTELES.values()), key="w_estrellas", on_change=cambiar_paquete, horizontal=True,
                     disabled=estado.w_noches == NOCHES[0])
        llegada = resultado.perfil.llega_a_cusco
        if llegada != "antes":
            motivo = "llega a Cusco el mismo día del trek" if llegada == "mismo_dia" else "no dice cuándo llega a Cusco"
            st.caption(f":material/auto_awesome: Sugerido: {motivo}. Una noche antes ayuda a aclimatarse a la altura. "
                       "Incluye el traslado del aeropuerto.")
        st.radio("Forma de pago", list(pagos.values()), key="w_metodo", on_change=cambiar_paquete, horizontal=True)
        st.html(html_desglose(resultado.paquete))
        st.caption("Al cambiar el paquete, el borrador se vuelve a armar (se pierden los cambios hechos a mano).")


def registrar_consulta(estado: str) -> None:
    """Guarda el perfil agregado de la consulta para el Tablero (sin texto ni teléfono)."""
    fila = registro_desde_resultado(st.session_state.resultado, estado, hoy_en_lima(),
                                    contar_registradas(RUTA_REGISTRO) + 1)
    registrar(fila, RUTA_REGISTRO)
    st.session_state.registrada = estado
    st.toast(f"Consulta registrada como {estado}. Ya cuenta en el Tablero.", icon=":material/check_circle:")
    celebrar(leer_registradas(RUTA_REGISTRO), hoy_en_lima())


def mostrar_borrador(resultado, telefono: str) -> None:
    """(1) Lo que se envía: el borrador editable y el botón de WhatsApp."""
    with st.container(border=True, key="tarjeta_borrador"):
        rotulo("Respuesta lista para enviar")
        if resultado.segundos is not None and st.session_state.get("origen") == "modelo":
            segundos = f"{resultado.segundos:.1f}".replace(".", ",")
            st.html(f'<span class="cronometro">Respuesta lista en {segundos} s</span>')
        texto = st.text_area("Revisa el mensaje y edítalo si hace falta", key="borrador", height=230)
        st.caption(f"{len(texto.split())} palabras · se envía desde tu WhatsApp, nada sale solo")
        # Justo encima del botón, para que se vea sin bajar.
        st.caption(f"Respondió: {resultado.uso.modelos_que_respondieron()} · Tokens usados: "
                   f"{resultado.uso.tokens_entrada} de entrada y {resultado.uso.tokens_salida} de salida "
                   f"(2 llamadas al modelo).")
        st.link_button("Abrir en WhatsApp", enlace_whatsapp(texto, telefono), type="primary",
                       icon=":material/send:", disabled=not texto.strip(), width="stretch")
        registrada = st.session_state.get("registrada")
        with st.container(horizontal=True, vertical_alignment="center", key="registro"):
            for estado in ("cotizada", "reservada"):
                st.button(f"Registrar como {estado}", type="tertiary", key=f"registrar_{estado}",
                          on_click=registrar_consulta, args=(estado,), disabled=bool(registrada),
                          help="Guarda solo el perfil de la consulta para el Tablero, sin el mensaje ni el teléfono.")
        if registrada:
            st.caption(f":material/check: Registrada como {registrada}.")


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
        st.button("Ver fuentes y verificación", type="tertiary", icon=":material/fact_check:",
                  on_click=ir_a, args=("Fuentes y verificación",))


def mostrar_perfil(perfil) -> None:
    """(4) Perfil del viajero en fichas compactas; lo que falta, como etiquetas."""
    with st.container(border=True, key="tarjeta_perfil"):
        rotulo("Lo que entendimos del viajero")
        st.html(html_perfil(perfil))


def mostrar_respuesta_nocturna(resultado) -> None:
    """Simulación del modo nocturno: lo que se enviaría solo si la consulta llega fuera de horario."""
    nocturna = respuesta_nocturna(resultado.perfil, st.session_state.tarifario, advertencias_de_control(resultado),
                                  st.session_state.agencia, st.session_state.apertura)
    with st.container(border=True, key="tarjeta_nocturna"):
        rotulo("Respuesta automática fuera de horario")
        clase = "estado-envia" if nocturna.se_enviaria_sola else "estado-espera"
        st.html(f'<div class="nocturna-cabecera"><span class="estado {clase}">{nocturna.estado}</span>'
                f'<span class="simulacion">{ETIQUETA_SIMULACION}</span></div>')
        if nocturna.motivos:
            st.html('<p class="nocturna-motivo"><strong>Motivo:</strong> '
                    + " ".join(html.escape(m) for m in nocturna.motivos) + "</p>")
        st.html(f'<div class="nocturna-mensaje">{html.escape(nocturna.mensaje)}</div>')
        st.caption(f"Llegó a las {st.session_state.hora_llegada:%H:%M} (hora de Lima), fuera de tu horario "
                   f"de {st.session_state.apertura:%H:%M} a {st.session_state.cierre:%H:%M}. No se envió nada.")


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
        with st.container(horizontal=True):
            telefono = st.text_input("WhatsApp del viajero (opcional, con código de país)",
                                     placeholder="+1 555 123 4567")
            st.session_state.hora_llegada = st.time_input(
                "Hora de llegada de la consulta", st.session_state.hora_llegada, step=60,
                help="Hora de Lima. Fuera de tu horario de atención, con el modo nocturno activo, "
                     "se muestra la respuesta automática que se enviaría.")
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
        if not es_ejemplo:  # para "Estado del sistema": cuántas consultas al modelo en esta sesión
            st.session_state.consultas_modelo = st.session_state.get("consultas_modelo", 0) + 1
        st.session_state.registrada = None
        iniciar_paquete()

    if st.session_state.get("resultado") and st.session_state.pop("recomponer", False):
        componer_paquete()  # cambiaron los extras o los recargos en "Mi agencia"
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

    llegada = datetime.combine(hoy_en_lima(), st.session_state.hora_llegada)  # sin zona = hora de Lima
    if st.session_state.modo_nocturno and fuera_de_horario(llegada, st.session_state.apertura, st.session_state.cierre):
        mostrar_respuesta_nocturna(resultado)

    # Laptop: borrador y opciones lado a lado. Celular: una columna, el borrador primero.
    izquierda, derecha = st.columns([7, 5], gap="large")
    with izquierda:
        mostrar_borrador(resultado, telefono)
    with derecha:
        mostrar_avisos(resultado)
        mostrar_paquete(resultado)
        mostrar_opciones(resultado)
    mostrar_perfil(resultado.perfil)


# ---------------------------------------------------------------- Fuentes y verificación
CARPETA_BASE = RAIZ / "data" / "knowledge"


def ir_a(destino: str) -> None:
    st.session_state.pagina = destino


def html_enlaces(urls: list[str]) -> str:
    """Cada fuente como enlace con su dominio; las del Estado peruano, marcadas como oficiales."""
    if not urls:
        return '<span class="sin-fuente">Sin fuente indicada</span>'
    enlaces = []
    for url in urls:
        oficial = '<span class="etiqueta etiqueta-oficial">Oficial</span>' if es_oficial(url) else ""
        enlaces.append(f'<a href="{html.escape(url)}" target="_blank" rel="noopener">{html.escape(dominio(url))}</a>'
                       f"{oficial}")
    return '<ul class="enlaces">' + "".join(f"<li>{e}</li>" for e in enlaces) + "</ul>"


def html_etiqueta_fecha(actualizado: str, dias: int | None, verificar: bool) -> str:
    if verificar:
        detalle = "sin fecha" if dias is None else f"hace {dias} días"
        return f'<span class="etiqueta etiqueta-verificar">{ETIQUETA_VERIFICAR} · {detalle}</span>'
    cuando = "hoy" if dias == 0 else ("ayer" if dias == 1 else f"hace {dias} días")
    return f'<span class="fuente-fecha">Actualizado el {html.escape(actualizado)} ({cuando})</span>'


def mostrar_fuentes_usadas(resultado, hoy) -> None:
    usadas = fuentes_usadas(resultado.fragmentos, hoy)
    a_verificar = sum(u.verificar for u in usadas)
    with st.container(border=True, key="tarjeta_fuentes"):
        rotulo("Lo que se usó en la última consulta")
        consulta = st.session_state.get("consulta", "")
        if consulta:
            st.caption(f"Consulta: «{consulta[:140]}{'…' if len(consulta) > 140 else ''}»")
        if a_verificar:
            st.warning(f"**{a_verificar} de {len(usadas)} fragmentos tienen más de {DIAS_PARA_VERIFICAR} días.** "
                       "Confirma esos datos en la fuente antes de enviar la respuesta.", icon=":material/history:")
        else:
            st.success(f"Los {len(usadas)} fragmentos se actualizaron en los últimos {DIAS_PARA_VERIFICAR} días.",
                       icon=":material/verified:")
        filas = []
        for u in usadas:
            filas.append(
                f'<div class="fuente{" fuente-verificar" if u.verificar else ""}">'
                f'<div class="fuente-cabecera"><span class="fuente-titulo">{html.escape(u.titulo)}</span>'
                f'<code>{html.escape(u.archivo)}.md</code></div>'
                f'{html_etiqueta_fecha(u.actualizado, u.dias, u.verificar)}'
                f'{html_enlaces(u.fuentes)}</div>')
        st.html('<div class="fuentes">' + "".join(filas) + "</div>")


def html_tabla_base(tabla: pd.DataFrame) -> str:
    filas = []
    for fila in tabla.itertuples():
        fecha = html.escape(fila.actualizado or "—")
        if fila.verificar:
            fecha += f'<br><span class="etiqueta etiqueta-verificar">{ETIQUETA_VERIFICAR}</span>'
        filas.append(f'<tr><td><strong>{html.escape(fila.tema)}</strong><br><code>{html.escape(fila.archivo)}.md</code>'
                     f'<div class="tabla-estado">{html.escape(fila.estado)}</div></td>'
                     f'<td class="tabla-fecha">{fecha}</td><td class="tabla-num">{fila.fragmentos}</td>'
                     f"<td>{html_enlaces(fila.fuentes)}</td></tr>")
    return ('<div class="tabla-desliza"><table class="tabla-base"><thead><tr><th>Archivo</th><th>Actualizado</th>'
            '<th>Fragmentos</th><th>Fuentes</th></tr></thead><tbody>' + "".join(filas) + "</tbody></table></div>")


def pagina_fuentes() -> None:
    st.header("Fuentes y verificación")
    st.html('<p class="subtitulo">De dónde sale cada dato de la respuesta. Lo que tiene más de '
            f'{DIAS_PARA_VERIFICAR} días se marca para verificar antes de enviarlo.</p>')
    hoy = hoy_en_lima()
    resultado = st.session_state.get("resultado")
    if resultado is None:
        st.html('<div class="vacio"><strong>Todavía no hay una consulta.</strong> Cuando prepares una respuesta, '
                'aquí verás qué fragmentos de la base de conocimiento se usaron, su fecha y su fuente.</div>')
        st.button("Ir a Nueva consulta", type="primary", icon=":material/edit_note:", on_click=ir_a,
                  args=("Nueva consulta",), key="fuentes_ir_consulta")
    else:
        if st.session_state.get("origen") in ("ejemplo", "sin_cuota"):
            st.info("Es el ejemplo guardado: estos son los fragmentos que se usaron en esa consulta.",
                    icon=":material/bookmark:")
        mostrar_fuentes_usadas(resultado, hoy)

    tabla = tabla_base(CARPETA_BASE, hoy)
    with st.container(border=True, key="tarjeta_base"):
        rotulo("Base de conocimiento completa")
        texto = st.text_input("Buscar por tema, archivo o fuente", placeholder="Por ejemplo: permisos, elperuano, lares",
                              key="buscar_base")
        encontrados = buscar_en_base(tabla, texto)
        st.caption(f"{len(encontrados)} de {len(tabla)} archivos · {int(tabla['fragmentos'].sum())} fragmentos · "
                   f"{int(tabla['oficiales'].sum())} enlaces a fuentes oficiales")
        if encontrados.empty:
            st.info("Ningún archivo coincide con la búsqueda.", icon=":material/search_off:")
        else:
            st.html(html_tabla_base(encontrados))


# ---------------------------------------------------------------- Estado del sistema
ORIGENES = {
    "modelo": "No: respondió el modelo",
    "ejemplo": "Sí: botón «Usar mensaje de ejemplo»",
    "sin_cuota": "Sí: el modelo no tenía cuota",
}


@st.cache_data
def pruebas_automaticas() -> tuple[int, int]:
    return contar_pruebas(RAIZ / "tests")


def modelos_sin_cuota() -> set[str]:
    """Solo si ya se creó el modelo en esta sesión (no crea el cliente ni llama a la API)."""
    if not st.session_state.get("consultas_modelo") or falta_clave():
        return set()
    return set(getattr(modelo(proveedor()), "_agotados", set()))


def pagina_estado() -> None:
    st.header("Estado del sistema")
    st.html('<p class="subtitulo">Qué está funcionando ahora y con qué datos. Para la demo y para saber '
            'cuánto confiar en la respuesta.</p>')
    estado = st.session_state
    resultado, origen = estado.get("resultado"), estado.get("origen")
    nombre = proveedor()
    configurados = modelos_configurados(nombre)
    with st.container(key="estado_sistema"):  # la clave es para el CSS de las cifras (ver estilo.css)

        c1, c2, c3 = st.columns(3)
        with c1:
            respondio = resultado.uso.modelos_que_respondieron() if resultado else "Sin consulta todavía"
            st.metric("Modelo que respondió", respondio, border=True,
                      help="En la última consulta. Si fue el ejemplo guardado, es el modelo de esa consulta.")
            st.caption(f"Configurado: {' → '.join(configurados)} ({nombre})"
                       + (f" · falta {falta_clave()}" if falta_clave() else ""))
        with c2:
            quedan = consultas_restantes(nombre, modelos_sin_cuota())
            st.metric("Consultas que quedan hoy", "No se conoce" if quedan is None else quedan, border=True,
                      help="La API no informa la cuota restante.")
            st.caption(f"{referencia_cuota(nombre)} En esta sesión: {estado.get('consultas_modelo', 0)}.")
        with c3:
            st.metric("¿Se usó el ejemplo guardado?", ORIGENES.get(origen, "Sin consulta todavía").split(":")[0],
                      border=True)
            st.caption(ORIGENES[origen].split(": ", 1)[1].capitalize() + "."
                       if origen in ORIGENES else "Todavía no se preparó ninguna respuesta.")

        base = version_base(CARPETA_BASE)
        ahora = datetime.now(ZONA)
        fuera = fuera_de_horario(ahora, estado.apertura, estado.cierre)
        c4, c5, c6 = st.columns(3)
        with c4:
            st.metric("Base de conocimiento", f"v. {base.version}", border=True,
                      help="Huella del contenido: cambia si se edita cualquier archivo de data/knowledge.")
            st.caption(f"Actualizada el {base.actualizada} · {base.archivos} archivos · {base.fragmentos} fragmentos.")
        with c5:
            st.metric("Hora en Lima", f"{ahora:%H:%M}", border=True)
            if not estado.modo_nocturno:
                nocturno = "Modo nocturno apagado."
            elif fuera:
                nocturno = "Modo nocturno activo: ahora es fuera de horario (simulado, no envía nada)."
            else:
                nocturno = "Modo nocturno encendido; se activa al cerrar."
            st.caption(f"{nocturno} Horario: {estado.apertura:%H:%M} a {estado.cierre:%H:%M}.")
        with c6:
            pruebas, archivos = pruebas_automaticas()
            st.metric("Pruebas automáticas", pruebas, border=True,
                      help="Contadas en tests/, sin ejecutarlas. Para correrlas: python -m unittest discover tests")
            st.caption(f"En {archivos} archivos de tests/. Se cuentan, no se ejecutan desde la app.")


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

    with st.container(border=True, key="tarjeta_horario"):
        rotulo("Horario de atención (hora de Lima)")
        with st.container(horizontal=True, vertical_alignment="bottom"):
            st.session_state.apertura = st.time_input("Abre", st.session_state.apertura, step=1800)
            st.session_state.cierre = st.time_input("Cierra", st.session_state.cierre, step=1800)
            st.session_state.modo_nocturno = st.toggle(
                "Modo nocturno", st.session_state.modo_nocturno,
                help="Fuera de horario, muestra la primera respuesta segura que se enviaría sola. "
                     "Hoy es una simulación: no se envía nada.")
        st.caption("Con el modo nocturno, una consulta que llega fuera de horario recibe una respuesta armada por "
                   "código (precio desde tu tarifario, qué incluye y lo que falta preguntar) solo si el control "
                   "no encontró problemas. Si no, queda en espera del vendedor.")

    with st.container(border=True, key="tarjeta_meta"):
        rotulo("Meta semanal")
        st.session_state.meta_semanal = st.number_input(
            "Consultas respondidas por semana", 1, 500, int(st.session_state.meta_semanal), step=1,
            help="Cuentan las consultas que registras como cotizadas o reservadas, de lunes a domingo.")
        st.caption('Tu avance aparece arriba del Tablero, en "Mi semana".')

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

    with st.container(border=True, key="tarjeta_extras"):
        rotulo("Extras y días en Cusco")
        st.caption("Unidad: por persona, por noche (cada persona, cada noche) o por grupo. Aplica a: todos, "
                   "machu_picchu (treks que llegan), rutas separadas por punto y coma, o modulo_cusco "
                   "(hotel y traslado de los días en Cusco).")
        editado = st.data_editor(
            st.session_state.extras_base, num_rows="dynamic", width="stretch", key="editor_extras", hide_index=True,
            column_config={
                "extra_id": st.column_config.TextColumn("Código"),
                "extra": st.column_config.TextColumn("Extra", width="medium"),
                "unidad": st.column_config.SelectboxColumn("Unidad", options=list(UNIDADES), required=True),
                "precio_usd": st.column_config.NumberColumn("US$", min_value=0, format="%.2f"),
                "aplica_a": st.column_config.TextColumn("Aplica a"),
                "beneficio_para_el_viajero": st.column_config.TextColumn("Beneficio para el viajero", width="large"),
                "origen_precio": st.column_config.TextColumn("De dónde sale el precio", width="large"),
            })
        with st.container(horizontal=True, vertical_alignment="bottom"):
            recargos = {"transferencia": 0.0}
            recargos["tarjeta"] = st.number_input("Recargo con tarjeta (%)", 0.0, 30.0,
                                                  float(st.session_state.recargos["tarjeta"]), step=0.5)
            recargos["paypal"] = st.number_input("Recargo con PayPal (%)", 0.0, 30.0,
                                                 float(st.session_state.recargos["paypal"]), step=0.5)
            st.download_button("Descargar extras", editado.to_csv(index=False).encode("utf-8"),
                               file_name="extras.csv", mime="text/csv", icon=":material/download:")
        if not editado.equals(st.session_state.extras) or recargos != st.session_state.recargos:
            st.session_state.extras, st.session_state.recargos = editado, recargos
            st.session_state.recomponer = True  # el paquete de la consulta abierta se recalcula


# ---------------------------------------------------------------- Tablero
PRIMARIO, TONO_VERDE, OCRE, TINTA, SECUNDARIO, SUAVE = "#1E6B52", "#5E9C84", "#C9741D", "#15302B", "#5B6F6A", "#E8F0EC"


def grafico(chart: alt.Chart, titulo: str, subtitulo: str = "") -> alt.Chart:
    """Ejes y títulos legibles a distancia, con la tipografía y los colores del sistema."""
    return (chart.properties(title=alt.TitleParams(titulo, subtitle=subtitulo or alt.Undefined), height=280)
            .configure_title(font="Montserrat", fontSize=18, color=TINTA, anchor="start", subtitleFont="Nunito",
                             subtitleFontSize=13, subtitleColor=SECUNDARIO, offset=12)
            .configure_axis(labelFont="Nunito", labelFontSize=13, labelColor=SECUNDARIO, titleFont="Nunito",
                            titleFontSize=13, titleColor=SECUNDARIO, gridColor=SUAVE, domainColor="#D6E0DD",
                            tickColor="#D6E0DD")
            .configure_view(stroke=None))


def porcentaje(valor: float) -> str:
    return f"{valor * 100:.1f} %".replace(".", ",")


# ---------------------------------------------------------------- Mi semana
def ir_a_consulta() -> None:
    st.session_state.pagina = "Nueva consulta"


def celebrar(registradas, hoy) -> None:
    """Logros reales, una vez por semana: meta cumplida y nueva mejor semana. Toast breve, sin globos."""
    if registradas.empty:
        return
    lunes = inicio_semana(hoy).isoformat()
    meta = progreso_meta(registradas, hoy, st.session_state.meta_semanal)
    if meta.cumplida and not st.session_state.get(f"celebrada_meta_{lunes}"):
        st.session_state[f"celebrada_meta_{lunes}"] = True
        st.toast(f"Cumpliste tu meta: {meta.respondidas} consultas respondidas esta semana. ¡Bien hecho!",
                 icon=":material/flag:")
    s = semana(registradas, hoy)
    if s.supera_mejor and not st.session_state.get(f"celebrada_mejor_{lunes}"):
        st.session_state[f"celebrada_mejor_{lunes}"] = True
        st.toast(f"Tu mejor semana: {usd(s.esta)} reservados, más que tus {usd(s.mejor_anterior)} anteriores.",
                 icon=":material/trending_up:")


def cerrar_cotizacion(id_consulta: str, estado: str) -> None:
    hoy = hoy_en_lima()
    cambiar_estado(RUTA_REGISTRO, id_consulta, estado, hoy)
    st.toast(f"Cotización marcada como {estado}.", icon=":material/check_circle:")
    celebrar(leer_registradas(RUTA_REGISTRO), hoy)


def plural(n: int, singular: str, plural_: str) -> str:
    return f"{n} {singular if n == 1 else plural_}"


def texto_racha(r) -> str:
    if r.registro_hoy:
        if r.dias == 1:
            return "Hoy registraste consultas: es el primer día de tu racha."
        return f"Llevas {r.dias} días seguidos registrando consultas."
    if r.dias:
        return (f"Llevas {plural(r.dias, 'día seguido', 'días seguidos')} registrando consultas. Hoy todavía no "
                "registraste ninguna: cuando respondas la próxima, regístrala y la racha sigue.")
    return "Hoy todavía no registraste consultas. Cuando respondas una, regístrala y empiezas una racha."


def mostrar_mi_semana() -> None:
    """Solo las consultas registradas en la app (nunca las sintéticas). El vendedor contra sí mismo."""
    hoy = hoy_en_lima()
    registradas = leer_registradas(RUTA_REGISTRO)
    with st.container(border=True, key="mi_semana"):
        rotulo("Mi semana")
        if registradas.empty:
            st.markdown("Registra tus consultas y aquí verás cuánto vendes, qué treks te piden y qué cotizaciones "
                        "esperan seguimiento.")
            st.button("Ir a Nueva consulta", type="primary", icon=":material/edit_note:", on_click=ir_a_consulta)
            return

        meta = progreso_meta(registradas, hoy, st.session_state.meta_semanal)
        s = semana(registradas, hoy)
        izquierda, derecha = st.columns([2, 3], gap="large")
        with izquierda:
            if s.variacion > 0:
                delta, color = f"+{usd(s.variacion)} frente a la semana anterior", "normal"
            elif s.variacion < 0:
                delta, color = f"-{usd(-s.variacion)} frente a la semana anterior", "normal"
            else:
                delta, color = "Igual que la semana anterior", "off"
            st.metric("Reservados esta semana", usd(s.esta), delta, delta_color=color)
            if s.supera_mejor:
                st.caption(f":material/trending_up: Tu mejor semana hasta ahora (antes: {usd(s.mejor_anterior)}).")
        with derecha:
            st.progress(meta.fraccion, text=f"**{meta.respondidas} de {meta.meta}** respondidas esta semana")
            if meta.cumplida:
                st.caption(":material/flag: Meta cumplida esta semana.")
            else:
                st.caption(f"Te {'falta' if meta.faltan == 1 else 'faltan'} {meta.faltan} para tu meta "
                           "(la cambias en Mi agencia).")
            st.caption(f":material/local_fire_department: {texto_racha(racha(registradas, hoy))}")

        esperan = pendientes(registradas, hoy)
        if not esperan.empty:
            with st.container(border=True, key="seguimiento"):
                st.markdown(f"**{plural(len(esperan), 'cotización espera', 'cotizaciones esperan')} seguimiento**")
                for fila in esperan.itertuples():
                    personas = pd.to_numeric(fila.personas, errors="coerce")
                    detalle = [NOMBRE_RUTA.get(fila.trek, fila.trek)]
                    if pd.notna(personas):
                        detalle.append(plural(int(personas), "persona", "personas"))
                    dias = (hoy - fila.fecha_estado).days
                    detalle.append(f"cotizada el {fila.fecha_estado:%d/%m} (hace {dias} días)")
                    with st.container(horizontal=True, vertical_alignment="center"):
                        st.markdown(" · ".join(detalle))
                        st.button("Reservada", key=f"reservar_{fila.id}", icon=":material/check:",
                                  on_click=cerrar_cotizacion, args=(fila.id, "reservada"))
                        st.button("Perdida", key=f"perder_{fila.id}", type="tertiary",
                                  on_click=cerrar_cotizacion, args=(fila.id, "perdida"))
        st.caption("Solo tus consultas registradas en esta app. Te comparas contigo: semana contra semana.")
    celebrar(registradas, hoy)


def pagina_tablero() -> None:
    st.header("Tablero")
    mostrar_mi_semana()
    st.html(f'<span class="sinteticos">{ETIQUETA_SINTETICOS}</span>')
    st.sidebar.html(f'<span class="sinteticos">{ETIQUETA_SINTETICOS}</span>')  # visible mientras se baja

    consultas = cargar_consultas(CONSULTAS_SINTETICAS, RUTA_REGISTRO)
    registradas = int((consultas["origen"] == "registrada").sum())
    st.html('<p class="subtitulo" style="margin-top:8px">Consultas de septiembre de 2025 a octubre de 2026'
            + (f", más {registradas} registradas en esta app" if registradas else "") + ".</p>")

    with st.container(horizontal=True):
        treks = st.multiselect("Trek", sorted(consultas["trek"].dropna().unique()), placeholder="Todos los treks",
                               format_func=lambda t: NOMBRE_RUTA.get(t, t))
        idiomas = st.multiselect("Idioma", sorted(consultas["idioma"].dropna().unique()),
                                 placeholder="Todos los idiomas", format_func=idioma)
    datos = filtrar(consultas, treks, idiomas)
    if datos.empty:
        st.info("No hay consultas con esos filtros.", icon=":material/filter_alt_off:")
        return

    m = metricas(datos)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Consultas", f"{m['consultas']:,}".replace(",", "\u202f"), border=True)
    c2.metric("Tasa de cierre", porcentaje(m["tasa_cierre"]), border=True,
              help="Reservadas ÷ consultas respondidas (cotizadas + reservadas).")
    c3.metric("Sin respuesta", m["sin_respuesta"], border=True,
              help=f"{porcentaje(m['pct_sin_respuesta'])} de las consultas no recibieron respuesta.")
    c4.metric("Monto reservado", usd(m["monto_reservado"]), border=True,
              help="Suma del total de las consultas reservadas.")

    meses = por_mes_viaje(datos)
    pico = int(meses["consultas"].max())
    barras_mes = alt.Chart(meses).mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4).encode(
        x=alt.X("mes_nombre:N", sort=list(meses["mes_nombre"]), title=None, axis=alt.Axis(labelAngle=0)),
        y=alt.Y("consultas:Q", title="Consultas"),
        color=alt.condition(alt.datum.consultas == pico, alt.value(OCRE), alt.value(PRIMARIO)),
        tooltip=[alt.Tooltip("mes_nombre:N", title="Mes"), alt.Tooltip("consultas:Q", title="Consultas")],
    )
    st.altair_chart(grafico(barras_mes, "Consultas por mes del viaje", "En ocre, el mes con más consultas"),
                    theme=None, width="stretch")

    izquierda, derecha = st.columns(2, gap="large")
    with izquierda:
        treks_df = por_trek(datos)
        barras = alt.Chart(treks_df).mark_bar(cornerRadiusTopRight=4, cornerRadiusBottomRight=4, color=PRIMARIO).encode(
            y=alt.Y("trek:N", sort="-x", title=None), x=alt.X("consultas:Q", title="Consultas"),
            tooltip=[alt.Tooltip("trek:N", title="Trek"), alt.Tooltip("consultas:Q", title="Consultas")])
        st.altair_chart(grafico(barras, "Por trek"), theme=None, width="stretch")
    with derecha:
        paises = por_pais(datos)
        barras = alt.Chart(paises).mark_bar(cornerRadiusTopRight=4, cornerRadiusBottomRight=4, color=TONO_VERDE).encode(
            y=alt.Y("pais:N", sort="-x", title=None), x=alt.X("consultas:Q", title="Consultas"),
            tooltip=[alt.Tooltip("pais:N", title="País"), alt.Tooltip("consultas:Q", title="Consultas")])
        st.altair_chart(grafico(barras, "Por país", "Los 10 con más consultas"), theme=None, width="stretch")

    st.caption("Las consultas registradas desde la app no traen el país: cuentan como \"no indicado\". "
               "Se guarda solo el perfil de la consulta, nunca el mensaje ni el teléfono.")


{"Nueva consulta": pagina_consulta, "Tablero": pagina_tablero, "Fuentes y verificación": pagina_fuentes,
 "Mi agencia": pagina_agencia, "Estado del sistema": pagina_estado}[pagina]()
