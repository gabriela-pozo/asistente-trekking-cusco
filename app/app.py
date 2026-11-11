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
from mapa_ui import mostrar_mapa_del_resultado  # noqa: E402

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
    ORDEN_ESTADOS, PERIODOS, cargar_consultas, cierre_por_trek, contar_registradas, embudo, filtrar, hallazgo_embudo,
    hallazgo_horario, hallazgo_meses, hallazgo_paises, hallazgo_treks, metricas, paises_con_otros, pct, periodo,
    por_dia_y_hora, por_mes_y_estado, registrar, registro_desde_resultado, variaciones,
    APERTURA_H, CIERRE_H, PREGUNTA_TABLERO, por_dia_y_franja, texto_origen, titulo_embudo, titulo_horario,
    titulo_meses, titulo_paises, titulo_treks,
)
from core.whatsapp import enlace_whatsapp  # noqa: E402
from presentacion import (  # noqa: E402
    GUIA_NOTAS, GUIA_PASOS, html_chips, html_desglose, html_opciones_compactas, icono, idioma, lista_markdown,
    separar_advertencias, usd,
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
ETIQUETA_SINTETICOS = "Datos de demostración"
ETIQUETA_SIMULACION = "Simulación: el envío automático requiere la API de WhatsApp Business (siguiente paso)"

st.set_page_config(page_title="Abra Travel", page_icon=ICONO, layout="wide")


@st.cache_data
def estilo(version: float) -> str:  # la fecha del archivo invalida la caché al editar el CSS
    return (RAIZ / "app" / "estilo.css").read_text(encoding="utf-8")


# Se lee una vez (caché) y se aplica en cada recarga. st.html quita las etiquetas <style>; st.markdown no.
_CSS = RAIZ / "app" / "estilo.css"
st.markdown(f"<style>{estilo(_CSS.stat().st_mtime)}</style>", unsafe_allow_html=True)


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
# Navegación: nombres cortos; los íconos los pone estilo.css (el radio conserva el nombre como valor).
PAGINAS = ["Consulta", "Tablero", "Fuentes", "Mi agencia", "Sistema", "Piloto"]
pagina = st.sidebar.radio("Ir a", PAGINAS, key="pagina", label_visibility="collapsed")
st.sidebar.html('<p class="pie-lateral"><span class="material-symbols-rounded">verified_user</span>'
                'Revisas cada respuesta antes de enviarla. Ningún mensaje se envía solo.</p>')


def estado_sistema_corto() -> str:
    """Insignia de la cabecera: qué modelo responde, o si lo que se ve es el ejemplo guardado."""
    if st.session_state.get("origen") in ("ejemplo", "sin_cuota"):
        return "Ejemplo guardado"
    if falta_clave():
        return "Sin clave: solo ejemplo"
    return f"Modelo: {modelos_configurados(proveedor())[0]}"


@st.dialog("¿Cómo se usa?")
def guia_rapida() -> None:
    for numero, (nombre_icono, texto) in enumerate(GUIA_PASOS, start=1):
        st.html(f'<div class="guia-paso"><b>{numero}</b><span>{html.escape(texto)}</span></div>')
    st.html('<ul class="guia-notas">' + "".join(f"<li>{html.escape(n)}</li>" for n in GUIA_NOTAS) + "</ul>")


def cabecera() -> None:
    """Barra superior de contexto, siempre visible: marca, agencia, UNA insignia de demo y el estado."""
    with st.container(horizontal=True, vertical_alignment="center", key="barra"):
        st.html(
            '<div class="barra-contenido">'
            f'<span class="barra-agencia">{html.escape(st.session_state.agencia)}</span>'
            f'<span class="insignia insignia-demo" title="Datos sintéticos: no son de ninguna agencia real">'
            f'{ETIQUETA_SINTETICOS}</span>'
            f'<span class="insignia insignia-estado">{html.escape(estado_sistema_corto())}</span>'
            '</div>')
        if st.button("¿Cómo se usa?", icon=":material/help:", key="guia", type="tertiary"):
            guia_rapida()


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
    """Paso 3, Ajustar: el resumen siempre visible y, cerrado, todo lo que se puede cambiar."""
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
    p = resultado.paquete

    with st.container(border=True, key="tarjeta_paquete"):
        rotulo("3 · Ajustar")
        st.html('<div class="resumen"><div><span class="resumen-total">' + usd(p.total_c / 100) + '</span>'
                '<span class="resumen-dato">total del grupo</span></div>'
                f'<div><span class="resumen-cifra">{usd(p.por_persona_c / 100)}</span>'
                '<span class="resumen-dato">por persona</span></div>'
                f'<div><span class="resumen-cifra">{usd(p.deposito_c / 100)}</span>'
                '<span class="resumen-dato">depósito (50 %)</span></div></div>')
        with st.expander("Ajustar paquete y extras", icon=":material/tune:"):
            st.selectbox("Trek base", bases, key="w_base", on_change=cambiar_paquete)
            pestana_extras, pestana_mas, pestana_desglose = st.tabs(["Extras", "Más opciones", "Desglose"])
            with pestana_extras:
                for _, e in aplicables.iterrows():
                    i = str(e["extra_id"])
                    st.checkbox(f"{e['extra']} · {usd(e['precio_usd'])} {e['unidad']}", key=f"w_extra_{i}",
                                on_change=cambiar_paquete, help=f"Precio: {e.get('origen_precio', '')}")
                    if i in sugeridos:
                        st.caption(f":material/auto_awesome: Sugerido por lo que escribió: {sugeridos[i].motivo}")
            with pestana_mas:
                st.markdown("**Días en Cusco antes del trek**")
                with st.container(horizontal=True):
                    st.radio("Noches", NOCHES, key="w_noches", on_change=cambiar_paquete, horizontal=True)
                    st.radio("Hotel", list(HOTELES.values()), key="w_estrellas", on_change=cambiar_paquete,
                             horizontal=True, disabled=estado.w_noches == NOCHES[0])
                llegada = resultado.perfil.llega_a_cusco
                if llegada != "antes":
                    motivo = ("llega a Cusco el mismo día del trek" if llegada == "mismo_dia"
                              else "no dice cuándo llega a Cusco")
                    st.caption(f":material/auto_awesome: Sugerido: {motivo}. Una noche antes ayuda a aclimatarse "
                               "a la altura. Incluye el traslado del aeropuerto.")
                st.radio("Forma de pago", list(pagos.values()), key="w_metodo", on_change=cambiar_paquete,
                         horizontal=True)
            with pestana_desglose:
                st.html(html_desglose(p))
            st.caption("Al cambiar el paquete, el borrador se vuelve a armar (se pierden los cambios hechos a mano).")


def registrar_consulta(estado: str) -> None:
    """Guarda el perfil agregado de la consulta para el Tablero (sin texto ni teléfono)."""
    fila = registro_desde_resultado(st.session_state.resultado, estado, hoy_en_lima(),
                                    contar_registradas(RUTA_REGISTRO) + 1)
    registrar(fila, RUTA_REGISTRO)
    st.session_state.registrada = estado
    st.toast(f"Consulta registrada como {estado}. Ya cuenta en el Tablero.", icon=":material/check_circle:")
    celebrar(leer_registradas(RUTA_REGISTRO), hoy_en_lima())


def boton_copiar(texto: str) -> None:
    """Botón "Copiar": Streamlit no tiene portapapeles propio, así que va en un componente mínimo (sin red)."""
    import json

    try:
        import streamlit.components.v1 as componentes
        _copiar_con_componente(componentes, json.dumps(texto))
    except Exception:  # noqa: BLE001 - si Streamlit quita el componente: el ícono de copiar de st.code
        with st.popover("Copiar", icon=":material/content_copy:"):
            st.code(texto, language=None, wrap_lines=True)


def _copiar_con_componente(componentes, texto_json: str) -> None:
    componentes.html(
        """<button id="b" style="width:100%;height:44px;border:1px solid #0B6E7F;border-radius:12px;background:#fff;
        color:#0B6E7F;font:700 16px Nunito,sans-serif;cursor:pointer">Copiar</button>
        <script>const t=__TEXTO__,b=document.getElementById('b');
        b.onclick=async()=>{try{await navigator.clipboard.writeText(t)}catch(e){const a=document.createElement('textarea');
        a.value=t;document.body.appendChild(a);a.select();document.execCommand('copy');a.remove()}
        b.textContent='Copiado';setTimeout(()=>b.textContent='Copiar',1800)}</script>""".replace("__TEXTO__", texto_json),
        height=48)


def mostrar_borrador(resultado, telefono: str) -> None:
    """Paso 2, Revisar: la respuesta como burbuja de WhatsApp, con Copiar y Abrir en WhatsApp."""
    with st.container(border=True, key="tarjeta_borrador"):
        etiqueta_idioma = (f'<span class="etiqueta-idioma">{icono("translate")}'
                           f'{html.escape(idioma(resultado.perfil.idioma))}</span>')
        meta = [etiqueta_idioma, f'<span class="hora">{datetime.now(ZONA):%H:%M}</span>']
        if resultado.segundos is not None and st.session_state.get("origen") == "modelo":
            segundos = f"{resultado.segundos:.1f}".replace(".", ",")
            meta.append(f'<span class="cronometro">Respuesta lista en {segundos} s</span>')
        st.html('<div class="burbuja-meta"><span class="rotulo">2 · Revisar la respuesta</span>' + "".join(meta) + "</div>")
        texto = st.text_area("Respuesta para el viajero (puedes editarla)", key="borrador", height=220,
                             label_visibility="collapsed")
        # Justo encima del botón, para que se vea sin bajar.
        st.caption(f"Respondió: {resultado.uso.modelos_que_respondieron()} · Tokens usados: "
                   f"{resultado.uso.tokens_entrada} de entrada y {resultado.uso.tokens_salida} de salida "
                   f"(2 llamadas al modelo).")
        enviar, copiar = st.columns([3, 2], gap="small")
        with enviar:
            st.link_button("Abrir en WhatsApp", enlace_whatsapp(texto, telefono), type="primary",
                           icon=":material/send:", disabled=not texto.strip(), width="stretch")
        with copiar:
            boton_copiar(texto)
        registrada = st.session_state.get("registrada")
        with st.container(horizontal=True, vertical_alignment="center", key="registro"):
            for estado in ("cotizada", "reservada"):
                st.button(f"Registrar como {estado}", type="tertiary", key=f"registrar_{estado}",
                          on_click=registrar_consulta, args=(estado,), disabled=bool(registrada),
                          help="Guarda solo el perfil de la consulta para el Tablero, sin el mensaje ni el teléfono.")
        if registrada:
            st.caption(f":material/check: Registrada como {registrada}. Alimenta el Tablero.")
        else:
            st.caption(":material/trending_up: Alimenta el Tablero")


def mostrar_avisos(resultado) -> None:
    """Advertencias para la agencia: un panel de máximo 3 viñetas; lo grave primero y en rojo."""
    graves, revisar = separar_advertencias(resultado.advertencias)
    todas = graves + revisar
    if not todas:
        st.html(f'<div class="aviso aviso-ok">{icono("check_circle")}<span>El control no encontró problemas. '
                'Igual lee el mensaje antes de enviarlo.</span></div>')
        return
    clase, nombre = ("aviso-grave", "error") if graves else ("aviso-revisar", "visibility")
    titulo = "Corrige antes de enviar" if graves else "Revisa antes de enviar"
    items = "".join(f"<li>{html.escape(a)}</li>" for a in todas[:3])
    st.html(f'<div class="aviso {clase}">{icono(nombre)}<div><strong>{titulo}</strong><ul>{items}</ul></div></div>')
    if len(todas) > 3:
        with st.expander(f"Ver las {len(todas)} advertencias"):
            st.markdown(lista_markdown(todas))


def mostrar_opciones(resultado) -> None:
    """Opciones del tarifario en dos líneas cada una; la información consultada vive en Fuentes."""
    rotulo("Opciones de tu tarifario")
    if not resultado.opciones:
        st.warning("Ninguna fila de tu tarifario encaja con esta consulta.")
    else:
        st.html(html_opciones_compactas(resultado.opciones))
    st.button(f"Información consultada ({len(resultado.fragmentos)})", type="tertiary", icon=":material/fact_check:",
              on_click=ir_a, args=("Fuentes",), key="ir_fuentes", help="Ver de dónde sale cada dato en Fuentes.")


def mostrar_perfil(perfil) -> None:
    """Lo que entendimos del viajero: chips pequeños con ícono."""
    rotulo("Lo que entendimos del viajero")
    st.html(html_chips(perfil))


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


def pasos(actual: int) -> None:
    nombres = ["Pegar", "Revisar", "Ajustar"]
    st.html('<ol class="pasos">' + "".join(
        f'<li class="{"activo" if i + 1 == actual else "hecho" if i + 1 < actual else ""}"><b>{i + 1}</b>{n}</li>'
        for i, n in enumerate(nombres)) + "</ol>")


def pagina_consulta() -> None:
    resultado = st.session_state.get("resultado")
    st.header("Nueva consulta")
    pasos(2 if resultado else 1)

    variable = falta_clave()
    if variable:
        st.warning(f"Falta la clave **{variable}** ({proveedor()}). Ponla en `.env` (ver `.env.example`). "
                   "Mientras tanto usa **Usar mensaje de ejemplo**.", icon=":material/key_off:")

    with st.container(border=True, key="tarjeta_entrada"):
        rotulo("1 · Pegar el mensaje del viajero")
        consulta = st.text_area("Mensaje del viajero", key="consulta", height=68 if resultado else 112, placeholder=EJEMPLO,
                                label_visibility="collapsed")
        with st.container(horizontal=True, vertical_alignment="center"):
            preparar = st.button("Preparar respuesta", type="primary", icon=":material/edit_note:",
                                 disabled=not consulta or bool(variable))
            st.button("Usar mensaje de ejemplo", type="tertiary", on_click=usar_ejemplo,
                      help="Muestra una consulta real ya resuelta. No gasta cuota del modelo.")
        with st.expander("Opciones", icon=":material/settings:"):
            telefono = st.text_input("WhatsApp del viajero (opcional, con código de país)",
                                     placeholder="+1 555 123 4567")
            st.session_state.hora_llegada = st.time_input(
                "Hora de llegada de la consulta", st.session_state.hora_llegada, step=60,
                help="Hora de Lima. Fuera de tu horario de atención, con el modo nocturno activo, "
                     "se muestra la respuesta automática que se enviaría.")

    if preparar:
        try:
            with st.status("Leyendo el mensaje → Buscando tu tarifa → Redactando", expanded=False) as avance:
                # Cadena de respaldo: modelo principal -> modelo de respaldo -> ejemplo guardado.
                resultado, es_ejemplo = responder_con_respaldo(
                    consulta, modelo(proveedor()), base_conocimiento(), st.session_state.tarifario,
                    st.session_state.extras, st.session_state.agencia)
                avance.update(label="Respuesta lista", state="complete")
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
        st.html('<div class="vacio"><strong>Aquí aparecerá la respuesta.</strong> Pega el mensaje y pulsa '
                '«Preparar respuesta».</div>')
        return

    origen = st.session_state.get("origen", "modelo")
    if origen == "sin_cuota":
        st.warning(f"**{AVISO_SIN_CUOTA}.** Este resultado no corresponde al mensaje que pegaste; "
                   "vuelve a intentarlo mañana.", icon=":material/hourglass_empty:")
    elif origen == "ejemplo":
        fecha = html.escape(str(st.session_state.get("fecha_ejemplo", "")))
        st.html(f'<span class="insignia insignia-guardado" title="No se llamó a la API, así que no gastó cuota.">'
                f'{icono("bookmark")}Resultado guardado · {fecha} · No se llamó a la API</span>')

    # Laptop: respuesta a la izquierda; lo entendido, advertencias y opciones a la derecha.
    izquierda, derecha = st.columns([7, 5], gap="large")
    with izquierda:
        mostrar_borrador(resultado, telefono)
    with derecha:
        mostrar_perfil(resultado.perfil)
        mostrar_avisos(resultado)
        mostrar_opciones(resultado)
    mostrar_paquete(resultado)

    llegada = datetime.combine(hoy_en_lima(), st.session_state.hora_llegada)  # sin zona = hora de Lima
    if st.session_state.modo_nocturno and fuera_de_horario(llegada, st.session_state.apertura, st.session_state.cierre):
        mostrar_respuesta_nocturna(resultado)
    mostrar_mapa_del_resultado(resultado)


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
                  args=("Consulta",), key="fuentes_ir_consulta")
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


def mayuscula(texto: str) -> str:
    return texto[:1].upper() + texto[1:]


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
            st.caption(mayuscula(ORIGENES[origen].split(": ", 1)[1]) + "."
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


# ---------------------------------------------------------------- Acerca del piloto
ALCANCE = [
    ("Es una demo con datos sintéticos",
     "Las consultas del Tablero son inventadas para mostrar cómo se vería: no son de ninguna agencia real. "
     "El ejemplo guardado sí es una consulta real al modelo, sin nombres ni teléfonos."),
    ("La agencia es ficticia; sus precios son de mercado",
     f"«{AGENCIA}» no existe. Su tarifario (7 treks en 3 niveles) se calculó con precios reales de mercado: "
     "el del Salkantay de 5 días, con 17 (12 publicados en webs de agencias y 5 cotizaciones recibidas por "
     "WhatsApp). El detalle está en docs/fuentes_precios.md."),
    ("Los precios los pone el código, no el modelo",
     "El modelo entiende el mensaje y redacta. Los montos salen de tu tarifario, y un control revisa que el "
     "borrador no tenga precios que no estén en la cotización."),
]
NO_HACE = [
    ("No envía mensajes solo",
     "«Abrir en WhatsApp» abre el mensaje en tu WhatsApp; lo envías tú. Nada sale de la app sin que lo hagas."),
    ("El modo nocturno es una simulación",
     "En esta app solo muestra la respuesta que se enviaría fuera de horario. Enviarla de verdad requiere la API "
     "de WhatsApp Business (hay un prototipo aparte con el sandbox de Twilio, no conectado a esta app)."),
    ("No reserva ni cobra",
     "No consulta cupos ni vende entradas a Machu Picchu o permisos del Camino Inca: eso se confirma en los "
     "sistemas oficiales."),
    ("No reemplaza información al día",
     f"La base de conocimiento tiene fecha y fuentes. Lo que tiene más de {DIAS_PARA_VERIFICAR} días se marca en "
     "«Fuentes y verificación» para revisarlo."),
]


def html_puntos(puntos: list[tuple[str, str]], clase: str) -> str:
    return (f'<ul class="puntos {clase}">' + "".join(
        f"<li><strong>{html.escape(t)}.</strong> {html.escape(d)}</li>" for t, d in puntos) + "</ul>")


def pagina_acerca() -> None:
    st.header("Acerca del piloto")
    st.html('<p class="subtitulo">Qué es Abra Travel hoy, qué no hace y quién decide.</p>')
    with st.container(border=True, key="tarjeta_revision"):
        st.html('<p class="revision"><strong>El vendedor siempre revisa.</strong> Abra Travel prepara un borrador; '
                'tú lo lees, lo corriges si hace falta y decides si lo envías.</p>')
    izquierda, derecha = st.columns(2, gap="large")
    with izquierda, st.container(border=True, key="tarjeta_alcance"):
        rotulo("Alcance")
        st.html(html_puntos(ALCANCE, "puntos-alcance"))
    with derecha, st.container(border=True, key="tarjeta_limites"):
        rotulo("Lo que no hace")
        st.html(html_puntos(NO_HACE, "puntos-limites"))
    st.caption("Las páginas «Fuentes y verificación» y «Estado del sistema» muestran de dónde sale cada dato y "
               "qué está funcionando en este momento.")


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
PRIMARIO, TONO_VERDE, OCRE, TINTA, SECUNDARIO, SUAVE = "#0B6E7F", "#66AFBD", "#C8660A", "#12303A", "#4A5F66", "#F5F1E8"


# Paleta validada (#0E7C58, #3A78C2, #C8660A) + el gris secundario del sistema. Un color fijo por estado en
# todos los gráficos: "sin respuesta" va en ocre porque es la pérdida que el Tablero quiere mostrar.
COLOR_ESTADO = {"reservada": "#0E7C58", "cotizada": "#3A78C2", "sin respuesta": "#C8660A", "perdida": "#5B6F6A"}
TEXTO_GRAFICO = 14  # px: legible en un proyector
MINIMO_RESPONDIDAS = 10  # como hallazgo_treks(): con menos, la tasa de cierre dice poco
CUADRICULA = "#E8E3D6"


def dibujar(grafico: alt.Chart, alto: int) -> None:
    """Estilo común: textos en tinta y gris verdoso, cuadrícula discreta, sin borde."""
    st.altair_chart(
        grafico.properties(height=alto, background="#FFFFFF")
        .configure_axis(labelFont="Nunito", labelFontSize=TEXTO_GRAFICO, labelColor=SECUNDARIO, titleFont="Nunito",
                        titleFontSize=TEXTO_GRAFICO, titleColor=SECUNDARIO, titleFontWeight="normal",
                        gridColor=CUADRICULA, domainColor="#DDD6C8", tickColor="#DDD6C8")
        .configure_legend(labelFont="Nunito", titleFont="Nunito", labelColor=TINTA, titleColor=SECUNDARIO,
                          labelFontSize=TEXTO_GRAFICO, titleFontSize=TEXTO_GRAFICO)
        .configure_view(stroke=None),
        theme=None, width="stretch")


def pregunta(titulo: str, hallazgo: str, corto: str = "") -> None:
    """La pregunta del dueño como rótulo; el título es la conclusión corta (≤ 8 palabras) y, debajo, la frase larga.

    Si no hay conclusión (p. ej., sin datos para ese gráfico), el título es la pregunta.
    """
    if corto or hallazgo:
        largo = f'<p class="hallazgo">{html.escape(hallazgo)}</p>' if hallazgo and hallazgo != corto else ""
        st.html(f'<p class="rotulo">{html.escape(titulo)}</p><h3 class="pregunta">{html.escape(corto or hallazgo)}</h3>'
                + largo)
    else:
        st.html(f'<h3 class="pregunta">{html.escape(titulo)}</h3>')


def tarjeta(nombre: str):
    return st.container(border=True, key=f"grafico_{nombre}")


TABLAS: list = []  # (nombre, tabla): se llena al dibujar cada gráfico y se muestra en la pestaña "Tablas"
TITULO_TABLA = {"embudo": "Embudo", "treks": "Por trek", "cuando_franjas": "Cuándo llegan (por franjas)",
                "cuando_escriben": "Cuándo llegan (hora por hora)", "meses": "Por mes del viaje", "paises": "Países"}


def ver_tabla(tabla, nombre: str) -> None:
    """Los mismos datos del gráfico, en tabla: se lee con lector de pantalla y sin depender del color."""
    TABLAS.append((nombre, tabla))


def mostrar_tablas() -> None:
    for nombre, tabla in TABLAS:
        st.markdown(f"**{TITULO_TABLA.get(nombre, nombre)}**")
        st.dataframe(tabla, hide_index=True, width="stretch")
        st.download_button("Descargar CSV", tabla.to_csv(index=False).encode("utf-8"), mime="text/csv",
                           file_name=f"tablero_{nombre}.csv", icon=":material/download:", key=f"descargar_{nombre}")


def miles(numero: float) -> str:
    return f"{int(numero):,}".replace(",", "\u202f")


def con_signo(numero: float, decimal: bool = False) -> str:
    texto = f"{abs(numero):.1f}".replace(".", ",") if decimal else miles(abs(numero))
    return ("+" if numero > 0 else "-" if numero < 0 else "") + texto


def usd_con_signo(monto: float) -> str:
    return ("+" if monto > 0 else "-" if monto < 0 else "") + usd(abs(monto))


def porcentaje(valor: float) -> str:
    return f"{valor * 100:.1f} %".replace(".", ",")


# ---------------------------------------------------------------- Mi semana
def ir_a_consulta() -> None:
    ir_a("Consulta")


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


META_INICIAL = 3  # meta chica para empezar a registrar (no es un dato: es una sugerencia)


def mostrar_mi_semana() -> None:
    """Solo las consultas registradas en la app (nunca las sintéticas). El vendedor contra sí mismo."""
    hoy = hoy_en_lima()
    registradas = leer_registradas(RUTA_REGISTRO)
    with st.container(border=True, key="mi_semana"):
        rotulo("Tu semana")
        if registradas.empty:  # corto y con una meta chica: el primer paso es registrar
            barra, texto, boton = st.columns([3, 5, 2], vertical_alignment="center")
            barra.progress(0, text=f"**0 de {META_INICIAL}** consultas registradas esta semana")
            texto.markdown("Registra tus consultas y aquí verás tu avance y lo que espera seguimiento.")
            boton.button("Ir a Nueva consulta", type="primary", icon=":material/edit_note:", on_click=ir_a_consulta)
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


def mapa_por_franjas(datos: pd.DataFrame) -> None:
    """7 días × 4 franjas con el número en cada celda. Madrugada y noche son las franjas fuera de horario."""
    f = por_dia_y_franja(datos)
    f["dia_corto"] = f["dia"].str[:3].str.capitalize()
    f["horario"] = f["fuera_de_horario"].map({True: "Fuera de horario", False: "En horario"})
    orden_dias, orden_franjas = list(dict.fromkeys(f["dia_corto"])), list(dict.fromkeys(f["franja"]))
    tope = max(int(f["consultas"].max()), 1)
    base = alt.Chart(f).encode(
        x=alt.X("franja:N", sort=orden_franjas, title=None,
                axis=alt.Axis(orient="bottom", labelAngle=0, ticks=False, domain=False, labelLimit=200,
                              labelExpr="split(datum.label, ' · ')")),  # dos líneas hacia abajo: entra a 390 px
        y=alt.Y("dia_corto:N", sort=orden_dias, title=None, axis=alt.Axis(ticks=False, domain=False)))
    celdas = base.mark_rect(cornerRadius=4, stroke="#FFFFFF", strokeWidth=2).encode(
        color=alt.Color("consultas:Q", scale=alt.Scale(range=["#E8F3F5", "#095866"], domain=[0, tope]),
                        legend=alt.Legend(title="Consultas", orient="bottom", gradientLength=160, tickMinStep=1,
                                          format="d")),
        tooltip=[alt.Tooltip("dia:N", title="Día"), alt.Tooltip("franja:N", title="Franja"),
                 alt.Tooltip("horario:N", title="Horario"), alt.Tooltip("consultas:Q", title="Consultas")])
    numeros = base.mark_text(font="Nunito", fontSize=TEXTO_GRAFICO + 2, fontWeight="bold").encode(
        text="consultas:Q",
        color=alt.condition(alt.datum.consultas > tope * 0.55, alt.value("#FFFFFF"), alt.value(TINTA)))
    dibujar(celdas + numeros, alto=230)
    st.caption(f"Madrugada (antes de las {APERTURA_H}:00) y noche (desde las {CIERRE_H}:00) son las franjas "
               "fuera de tu horario de atención.")
    tabla = f.pivot(index=["dia_n", "dia"], columns="franja", values="consultas")[orden_franjas]
    ver_tabla(tabla.reset_index().drop(columns="dia_n").rename(columns={"dia": "Día"}), "cuando_franjas")


def mapa_hora_por_hora(celdas: pd.DataFrame) -> None:
    """La vista detallada: 7 × 24 celdas, con el horario de atención recuadrado."""
    celdas = celdas.assign(dia_corto=celdas["dia"].str[:3].str.capitalize())
    orden_dias = list(dict.fromkeys(celdas["dia_corto"]))
    mapa = alt.Chart(celdas).mark_rect(cornerRadius=3, stroke="#FFFFFF", strokeWidth=1.5).encode(
        x=alt.X("hora:Q", scale=alt.Scale(domain=[0, 24], nice=False), title="Hora de llegada (Lima)",
                axis=alt.Axis(values=list(range(0, 25, 6)), labelExpr="datum.value + ':00'", grid=False)),
        x2="hora_fin:Q",
        y=alt.Y("dia_corto:N", sort=orden_dias, title=None, axis=alt.Axis(ticks=False, domain=False)),
        color=alt.Color("consultas:Q", scale=alt.Scale(range=["#E8F3F5", "#095866"]),
                        legend=alt.Legend(title="Consultas", orient="bottom", gradientLength=140,
                                          tickMinStep=1, format="d")),
        tooltip=[alt.Tooltip("dia:N", title="Día"), alt.Tooltip("franja:N", title="Hora"),
                 alt.Tooltip("consultas:Q", title="Consultas")])
    horario = alt.Chart(pd.DataFrame({"x": [APERTURA_H], "x2": [CIERRE_H]})).mark_rect(
        fillOpacity=0, stroke=TINTA, strokeWidth=1.5, strokeDash=[5, 3]).encode(x="x:Q", x2="x2:Q")
    rotulo_horario = alt.Chart(pd.DataFrame({"x": [(APERTURA_H + CIERRE_H) / 2],
                                             "t": [f"Horario {APERTURA_H}:00–{CIERRE_H}:00"]})).mark_text(
        baseline="bottom", dy=-4, color=TINTA, fontSize=TEXTO_GRAFICO, font="Nunito", fontWeight="bold").encode(
        x="x:Q", y=alt.value(0), text="t:N")
    dibujar(alt.layer(mapa, horario, rotulo_horario), alto=230)
    ver_tabla(celdas[["dia", "franja", "consultas"]].rename(columns={"dia": "Día", "franja": "Hora",
                                                                     "consultas": "Consultas"}), "cuando_escriben")


PERIODO_INICIAL = list(PERIODOS)[1]  # "Últimos 6 meses", como al abrir el Tablero


def quitar_filtros() -> None:
    st.session_state.filtro_treks, st.session_state.filtro_idiomas = [], []
    st.session_state.filtro_periodo = PERIODO_INICIAL


def pagina_tablero() -> None:
    TABLAS.clear()
    st.header("Tablero")
    consultas = cargar_consultas(CONSULTAS_SINTETICAS, RUTA_REGISTRO)
    st.html(f'<div class="banda"><span class="banda-pregunta">{html.escape(PREGUNTA_TABLERO)}</span>'
            f'<span class="banda-origen">Datos: {html.escape(texto_origen(consultas))}.</span></div>')
    mostrar_mi_semana()  # solo las consultas registradas por el vendedor; no la tocan los filtros de abajo

    c1, c2, c3 = st.columns([4, 4, 4], vertical_alignment="bottom")
    st.session_state.setdefault("filtro_periodo", PERIODO_INICIAL)  # sin default=: lo pone «Quitar filtros»
    with c1:
        seleccion = st.segmented_control("Período", list(PERIODOS), key="filtro_periodo", label_visibility="collapsed",
                                         format_func=lambda p: p.replace("Últimos ", ""))
    nombre_periodo = seleccion or PERIODO_INICIAL
    treks = c2.multiselect("Trek", sorted(consultas["trek"].dropna().unique()), placeholder="Todos los treks",
                           format_func=lambda t: NOMBRE_RUTA.get(t, t), key="filtro_treks", label_visibility="collapsed")
    idiomas = c3.multiselect("Idioma", sorted(consultas["idioma"].dropna().unique()),
                             placeholder="Todos los idiomas", format_func=idioma, key="filtro_idiomas",
                             label_visibility="collapsed")
    meses = PERIODOS[nombre_periodo]
    filtradas = filtrar(consultas, treks, idiomas)
    datos, anteriores, comparable, (desde, hasta) = periodo(filtradas, meses)
    if datos.empty:
        elegidos = [NOMBRE_RUTA.get(t, t) for t in treks] + [idioma(i) for i in idiomas]
        st.info(f"**Ninguna consulta cumple a la vez: {' + '.join(elegidos)}.** Elige otro trek u otro idioma, "
                "o quita los filtros para ver todas.", icon=":material/filter_alt_off:")
        st.button("Quitar filtros", icon=":material/filter_alt_off:", on_click=quitar_filtros, key="quitar_filtros")
        return
    registradas = int((datos["origen"] == "registrada").sum())
    st.caption(f"Del {desde:%d/%m/%Y} al {hasta:%d/%m/%Y}: {miles(len(datos))} consultas"
               + (f", {registradas} registradas en esta app" if registradas else "")
               + f". Cada indicador se compara con los {meses} meses anteriores.")

    # 1. ¿Cómo voy?
    st.html('<p class="rotulo pregunta-kpi">¿Cómo voy?</p>')
    m = metricas(datos)
    v = variaciones(datos, anteriores) if comparable else None
    k1, k2, k3, k4 = st.columns(4)
    with k1, st.container(key="kpi_consultas"):
        st.metric("Consultas", miles(m["consultas"]), border=True,
                  delta=None if v is None else f"{con_signo(v['consultas'])}"
                  + (f" ({con_signo(round(v['pct_consultas'] * 100))} %)" if v["pct_consultas"] is not None else ""),
                  help="Consultas recibidas en el período, frente al período anterior de igual largo.")
    with k2, st.container(key="kpi_cierre"):
        st.metric("Tasa de cierre", porcentaje(m["tasa_cierre"]), border=True,
                  delta=None if v is None else f"{con_signo(round(v['tasa_cierre_pp'], 1), decimal=True)} pp",
                  help="Reservadas ÷ consultas respondidas. La variación está en puntos porcentuales (pp).")
        st.caption(f"Reservadas ÷ respondidas: {miles(m['reservadas'])} ÷ {miles(m['respondidas'])}")
    with k3, st.container(key="kpi_sin_respuesta"):
        st.metric("Sin respuesta de la agencia", miles(m["sin_respuesta"]), border=True, delta_color="inverse",
                  delta=None if v is None else con_signo(v["sin_respuesta"]),
                  help=f"{porcentaje(m['pct_sin_respuesta'])} de las consultas no recibieron respuesta de la "
                       "agencia. Que baje es bueno.")
    with k4, st.container(key="kpi_monto"):
        st.metric("Monto reservado", usd(m["monto_reservado"]), border=True,
                  delta=None if v is None else usd_con_signo(v["monto_reservado"]),
                  help="Suma del total de las consultas reservadas, en dólares.")
    if v is None:
        st.caption(f"Sin variación: los datos no cubren los {meses} meses anteriores completos.")

    izquierda, derecha = st.columns(2, gap="medium")
    # 2. Embudo: dónde se cae el proceso
    with izquierda, tarjeta("embudo"):
        e = embudo(datos)
        pregunta("¿En qué paso se pierden las ventas?", hallazgo_embudo(e), titulo_embudo(e))
        e["porcentaje"] = [None if p is None or pd.isna(p) else pct(p) for p in e["pct_anterior"]]
        e["etiqueta"] = [miles(n) if pd.isna(p) else f"{miles(n)} · {p}"
                         for n, p in zip(e["numero"], e["porcentaje"])]
        barras = alt.Chart(e).mark_bar(cornerRadiusEnd=4, color=PRIMARIO).encode(
            y=alt.Y("etapa:N", sort=list(e["etapa"]), title=None, scale=alt.Scale(paddingInner=.45),
                    axis=alt.Axis(ticks=False, domain=False)),
            x=alt.X("numero:Q", title="Consultas", scale=alt.Scale(domain=[0, max(e["numero"]) * 1.45]),
                    axis=alt.Axis(tickMinStep=1, tickCount=5, format="d")),
            tooltip=[alt.Tooltip("etapa:N", title="Etapa"), alt.Tooltip("numero:Q", title="Consultas"),
                     alt.Tooltip("porcentaje:N", title="% de la etapa anterior")])
        etiquetas = barras.mark_text(align="left", dx=6, color=TINTA, fontSize=TEXTO_GRAFICO, font="Nunito").encode(
            text="etiqueta:N")
        dibujar(barras + etiquetas, alto=260)
        st.caption("Cada % compara la etapa con la anterior. Cotizadas: respondidas con un precio.")
        ver_tabla(e[["etapa", "numero", "porcentaje"]].rename(columns={
            "etapa": "Etapa", "numero": "Consultas", "porcentaje": "% de la etapa anterior"}), "embudo")

    # 3. Dónde se pierde: por trek
    with derecha, tarjeta("treks"):
        t = cierre_por_trek(datos)
        pregunta("¿En qué trek se pierden?", hallazgo_treks(t), titulo_treks(t))
        t["tasa"] = t["tasa_cierre"].map(pct)
        t["poca_base"] = t["respondidas"] < MINIMO_RESPONDIDAS
        t["etiqueta"] = [f"{pct(x)} cierre · n={n}" for x, n in zip(t["tasa_cierre"], t["respondidas"])]
        # Barras apiladas por estado (mismos colores que en todo el Tablero); la suma de cada barra = consultas.
        apilado = (datos.assign(nombre=datos["trek"].map(lambda x: NOMBRE_RUTA.get(x, x)))
                   .groupby(["nombre", "estado"]).size().rename("n").reset_index())
        apilado = apilado.merge(t[["nombre", "poca_base"]], on="nombre")
        apilado["orden"] = apilado["estado"].map(ORDEN_ESTADOS.index)
        estados = [x for x in ORDEN_ESTADOS if x in set(apilado["estado"])]
        eje_y = alt.Y("nombre:N", sort=list(t["nombre"]), title=None, scale=alt.Scale(paddingInner=.4),
                      axis=alt.Axis(ticks=False, domain=False, labelLimit=170))
        barras = alt.Chart(apilado).mark_bar(cornerRadius=3, stroke="#FFFFFF", strokeWidth=1).encode(
            y=eje_y,
            # Sin agregar (una fila por trek y estado ya viene contada): así la opacidad ve el campo poca_base.
            x=alt.X("n:Q", stack="zero", title="Consultas", scale=alt.Scale(domain=[0, max(t["consultas"]) * 2.1]),
                    axis=alt.Axis(tickMinStep=1, tickCount=5, format="d")),
            color=alt.Color("estado:N", scale=alt.Scale(domain=estados, range=[COLOR_ESTADO[x] for x in estados]),
                            legend=alt.Legend(title=None, orient="top", direction="horizontal", symbolType="square",
                                              columns=2)),  # en 2 columnas no se corta en el celular
            order=alt.Order("orden:Q", sort="ascending"),
            opacity=alt.condition(alt.datum.poca_base, alt.value(.35), alt.value(1)),
            tooltip=[alt.Tooltip("nombre:N", title="Trek"), alt.Tooltip("estado:N", title="Estado"),
                     alt.Tooltip("n:Q", title="Consultas")])
        etiquetas = alt.Chart(t).mark_text(align="left", dx=6, fontSize=TEXTO_GRAFICO, font="Nunito").encode(
            y=eje_y, x="consultas:Q", text="etiqueta:N",
            color=alt.condition(alt.datum.poca_base, alt.value(SECUNDARIO), alt.value(TINTA)),
            tooltip=[alt.Tooltip("nombre:N", title="Trek"), alt.Tooltip("consultas:Q", title="Consultas"),
                     alt.Tooltip("respondidas:Q", title="Respondidas"),
                     alt.Tooltip("reservadas:Q", title="Reservadas"), alt.Tooltip("tasa:N", title="Tasa de cierre")])
        dibujar(barras + etiquetas, alto=min(max(260, 34 * len(t) + 70), 320))
        st.caption(f"n = consultas respondidas. Atenuados: menos de {MINIMO_RESPONDIDAS} respondidas, "
                   "su tasa de cierre todavía dice poco.")
        ver_tabla(t[["nombre", "consultas", "respondidas", "reservadas", "tasa"]].rename(columns={
            "nombre": "Trek", "consultas": "Consultas", "respondidas": "Respondidas (n)", "reservadas": "Reservadas",
            "tasa": "Tasa de cierre"}), "treks")

    # 4. Cuándo llega: por franjas (más legible) o hora por hora
    with tarjeta("cuando"):
        pregunta("¿Cuándo llegan las consultas?", hallazgo_horario(datos), titulo_horario(datos))
        vista = st.radio("Vista", ["Por franjas", "Hora por hora"], horizontal=True, key="vista_horario",
                         label_visibility="collapsed")
        celdas = por_dia_y_hora(datos)
        if vista == "Por franjas":
            mapa_por_franjas(datos)
        else:
            mapa_hora_por_hora(celdas)
        sin_hora = len(datos) - int(celdas["consultas"].sum())
        if sin_hora:
            st.caption(f"{sin_hora} consultas registradas desde la app no tienen hora de llegada: "
                       "no están en este gráfico.")

    pestana_mas, pestana_tablas = st.tabs(["Más análisis", "Tablas"])
    with pestana_mas:
        izq_mas, der_mas = st.columns(2, gap="medium")
        # 5. ¿Para qué meses?
        with izq_mas, tarjeta("meses"):
            mes_estado = por_mes_y_estado(datos)
            pregunta("¿Para qué meses?", hallazgo_meses(mes_estado), titulo_meses(mes_estado))
            estados = [x for x in ORDEN_ESTADOS if x in set(mes_estado["estado"])]
            columnas = alt.Chart(mes_estado).mark_bar(cornerRadius=4, stroke="#FFFFFF", strokeWidth=2).encode(
                x=alt.X("mes_nombre:N", sort=list(dict.fromkeys(mes_estado["mes_nombre"])), title="Mes del viaje",
                        scale=alt.Scale(paddingInner=.35), axis=alt.Axis(labelAngle=0, ticks=False)),
                y=alt.Y("consultas:Q", title="Consultas", axis=alt.Axis(tickMinStep=1, tickCount=5, format="d")),
                color=alt.Color("estado:N", scale=alt.Scale(domain=estados, range=[COLOR_ESTADO[x] for x in estados]),
                                legend=alt.Legend(title=None, orient="top", direction="horizontal", labelFontSize=TEXTO_GRAFICO,
                                                  labelColor=TINTA, symbolType="square")),
                order=alt.Order("orden:Q", sort="ascending"),
                tooltip=[alt.Tooltip("mes_nombre:N", title="Mes"), alt.Tooltip("estado:N", title="Estado"),
                         alt.Tooltip("consultas:Q", title="Consultas")])
            dibujar(columnas, alto=280)
            sin_mes = len(datos) - int(mes_estado["consultas"].sum())
            if sin_mes:  # p. ej., registradas sin mes de viaje: así el total no parece no cuadrar con los KPIs
                st.caption(f"{sin_mes} {'consulta no dice' if sin_mes == 1 else 'consultas no dicen'} el mes del viaje: "
                           "no están en este gráfico.")
            tabla_meses = mes_estado.pivot(index=["mes", "mes_nombre"], columns="estado", values="consultas")
            ver_tabla(tabla_meses.reset_index().drop(columns="mes").rename(columns={"mes_nombre": "Mes"}), "meses")

        # 6. ¿De dónde escriben?
        with der_mas, tarjeta("paises"):
            p = paises_con_otros(datos)
            pregunta("¿De dónde escriben?", hallazgo_paises(p), titulo_paises(p))
            p["etiqueta"] = [f"{miles(n)} · {pct(x)}" for n, x in zip(p["consultas"], p["porcentaje"])]
            p["pct"] = p["porcentaje"].map(pct)
            barras = alt.Chart(p).mark_bar(cornerRadiusEnd=4).encode(
                color=alt.condition(alt.datum.pais == "Otros", alt.value("#5B6F6A"), alt.value(PRIMARIO)),
                y=alt.Y("pais:N", sort=list(p["pais"]), title=None, scale=alt.Scale(paddingInner=.45),
                        axis=alt.Axis(ticks=False, domain=False)),
                x=alt.X("consultas:Q", title="Consultas", scale=alt.Scale(domain=[0, max(p["consultas"]) * 1.35]),
                        axis=alt.Axis(tickMinStep=1, tickCount=5, format="d")),
                tooltip=[alt.Tooltip("pais:N", title="País"), alt.Tooltip("consultas:Q", title="Consultas"),
                         alt.Tooltip("pct:N", title="Del total")])
            etiquetas = barras.mark_text(align="left", dx=6, color=TINTA, fontSize=TEXTO_GRAFICO, font="Nunito").encode(
                text="etiqueta:N")
            dibujar(barras + etiquetas, alto=max(260, 30 * len(p) + 50))
            st.caption("Los 7 países con más consultas, de mayor a menor; el resto, sumado en «Otros» (en gris)."
                       + (" Las consultas registradas desde la app no traen el país: cuentan como \"no indicado\"."
                          if registradas else ""))
            ver_tabla(p[["pais", "consultas", "pct"]].rename(columns={"pais": "País", "consultas": "Consultas",
                                                                       "pct": "Del total"}), "paises")
    with pestana_tablas:
        mostrar_tablas()

    st.caption("Se guarda solo el perfil de cada consulta, nunca el mensaje ni el teléfono.")


cabecera()
{"Consulta": pagina_consulta, "Tablero": pagina_tablero, "Fuentes": pagina_fuentes,
 "Mi agencia": pagina_agencia, "Sistema": pagina_estado, "Piloto": pagina_acerca}[pagina]()
