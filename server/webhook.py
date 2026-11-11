"""Webhook del modo nocturno para WhatsApp (sandbox de Twilio).

Flujo:
  1. Twilio hace POST /whatsapp con el mensaje entrante (form-urlencoded: Body, From, MessageSid...).
  2. Se valida la firma X-Twilio-Signature con TWILIO_AUTH_TOKEN. Si no es válida: 403.
  3. Se responde de inmediato con un TwiML vacío (<Response></Response>): la respuesta no va en el TwiML.
  4. En segundo plano, solo si la consulta llega fuera del horario (8:00–20:00, hora de Lima) o con
     FORZAR_MODO_NOCTURNO=1: el modelo extrae el perfil (ai/llm.py), el código arma la respuesta segura
     (core/respuesta_nocturna.py) y se envía con la API de Twilio.
  5. Un mismo MessageSid no se responde dos veces (en memoria: se pierde si el servicio se reinicia).

El log no guarda textos ni teléfonos: solo el MessageSid, el idioma, el trek y el estado.

Variables de entorno: TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_FROM (whatsapp:+1...),
LLM_PROVIDER y su clave (GEMINI_API_KEY o ANTHROPIC_API_KEY), y opcionales FORZAR_MODO_NOCTURNO=1,
URL_PUBLICA (la URL exacta configurada en Twilio, para validar la firma) y AGENCIA_NOMBRE.

Correr en local:  uvicorn server.webhook:app --port 8000
"""
from __future__ import annotations

import logging
import os
import sys
import threading
from collections import OrderedDict
from datetime import datetime
from pathlib import Path
from typing import Callable, Protocol

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from fastapi import BackgroundTasks, FastAPI, Request, Response  # noqa: E402

from ai import prompts  # noqa: E402
from ai.fecha import ZONA, fecha_en_texto  # noqa: E402
from ai.schemas import PerfilTurista  # noqa: E402
from core.cotizacion import NOMBRE_RUTA, cargar_tarifario, treks_sin_precio  # noqa: E402
from core.respuesta_nocturna import (  # noqa: E402
    APERTURA, CIERRE, fuera_de_horario, mensaje_recepcion, respuesta_nocturna,
)

try:  # .env en local; en Render las variables vienen del panel
    from dotenv import load_dotenv

    load_dotenv(RAIZ / ".env")
except ImportError:
    pass

log = logging.getLogger("abra.webhook")
TWIML_VACIO = '<?xml version="1.0" encoding="UTF-8"?><Response></Response>'
MAXIMO_RECORDADOS = 5000  # MessageSid ya atendidos (los más antiguos se olvidan)
AGENCIA_POR_DEFECTO = "Andes Trek Demo"


class Enviador(Protocol):
    def enviar(self, para: str, texto: str) -> str: ...


class EnviadorTwilio:
    """Envía con la API de Twilio (twilio-python 9). El cliente se crea al primer envío."""

    def __init__(self, account_sid: str | None = None, auth_token: str | None = None, desde: str | None = None):
        self.account_sid = account_sid or os.getenv("TWILIO_ACCOUNT_SID", "")
        self.auth_token = auth_token or os.getenv("TWILIO_AUTH_TOKEN", "")
        self.desde = desde or os.getenv("TWILIO_WHATSAPP_FROM", "")
        self._cliente = None

    def enviar(self, para: str, texto: str) -> str:
        if self._cliente is None:
            from twilio.rest import Client

            self._cliente = Client(self.account_sid, self.auth_token)
        mensaje = self._cliente.messages.create(from_=self.desde, to=para, body=texto)
        return mensaje.sid


class Recordados:
    """MessageSid ya vistos, para no responder dos veces (Twilio puede repetir un webhook)."""

    def __init__(self, maximo: int = MAXIMO_RECORDADOS):
        self._vistos: OrderedDict[str, None] = OrderedDict()
        self._candado = threading.Lock()
        self.maximo = maximo

    def primera_vez(self, sid: str) -> bool:
        with self._candado:
            if sid in self._vistos:
                return False
            self._vistos[sid] = None
            if len(self._vistos) > self.maximo:
                self._vistos.popitem(last=False)
            return True


def url_publica(request: Request) -> str:
    """La URL con la que Twilio firmó: URL_PUBLICA si está; si no, la que ve el cliente (https detrás del proxy)."""
    fija = os.getenv("URL_PUBLICA", "").strip()
    if fija:
        return fija
    protocolo = request.headers.get("x-forwarded-proto", request.url.scheme).split(",")[0].strip()
    host = request.headers.get("x-forwarded-host") or request.headers.get("host") or request.url.netloc
    url = f"{protocolo}://{host}{request.url.path}"
    return url + (f"?{request.url.query}" if request.url.query else "")


def ahora_en_lima() -> datetime:
    return datetime.now(ZONA)


def modo_forzado() -> bool:
    return os.getenv("FORZAR_MODO_NOCTURNO", "").strip() == "1"


def crear_app(llm=None, enviador: Enviador | None = None, reloj: Callable[[], datetime] = ahora_en_lima,
              auth_token: str | None = None, tarifario=None) -> FastAPI:
    """Las dependencias se pueden reemplazar en las pruebas (modelo, envío, reloj)."""
    app = FastAPI(title="Abra Travel: modo nocturno", docs_url=None, redoc_url=None)
    recordados = Recordados()
    estado = {"llm": llm, "enviador": enviador, "tarifario": tarifario}

    def token() -> str:
        return auth_token if auth_token is not None else os.getenv("TWILIO_AUTH_TOKEN", "")

    def modelo():
        if estado["llm"] is None:
            from ai.llm import crear_llm

            estado["llm"] = crear_llm()
        return estado["llm"]

    def precios():
        if estado["tarifario"] is None:
            estado["tarifario"] = cargar_tarifario(RAIZ / "data" / "tarifario_demo.csv")
        return estado["tarifario"]

    def enviar(para: str, texto: str) -> str:
        if estado["enviador"] is None:
            estado["enviador"] = EnviadorTwilio()
        return estado["enviador"].enviar(para, texto)

    def responder(sid: str, texto: str, para: str) -> None:
        """En segundo plano: perfil -> respuesta segura -> envío. Nunca registra el texto ni el teléfono."""
        agencia = os.getenv("AGENCIA_NOMBRE") or AGENCIA_POR_DEFECTO
        try:
            sistema = prompts.sistema_extraer(fecha_en_texto(reloj().date()))
            perfil, _ = modelo().estructurado(sistema, texto, PerfilTurista)
            sin_precio = treks_sin_precio(perfil, precios())
            avisos = [f"{NOMBRE_RUTA.get(t, t)} no está en el tarifario." for t in sin_precio]
            nocturna = respuesta_nocturna(perfil, precios(), avisos, agencia)
            mensaje, resumen = nocturna.mensaje, f"estado={nocturna.estado} idioma={nocturna.idioma} " \
                                                  f"trek={(perfil.treks_de_interes or ['ninguno'])[0]}"
        except Exception as error:  # noqa: BLE001 - sin perfil, solo el acuse de recibo (en inglés)
            mensaje = mensaje_recepcion(PerfilTurista(idioma=""), agencia)
            resumen = f"estado=solo recepción motivo={type(error).__name__}"
        try:
            enviado = enviar(para, mensaje)
            log.info("respondido sid=%s %s envio=%s", sid, resumen, enviado)
        except Exception as error:  # noqa: BLE001
            log.error("no se pudo enviar sid=%s %s error=%s", sid, resumen, type(error).__name__)

    @app.get("/salud")
    def salud() -> dict:
        return {
            "estado": "ok",
            "horario_lima": f"{APERTURA:%H:%M}-{CIERRE:%H:%M}",
            "modo_forzado": modo_forzado(),
            "twilio_configurado": all(os.getenv(v) for v in
                                      ("TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_WHATSAPP_FROM")),
        }

    @app.post("/whatsapp")
    async def whatsapp(request: Request, tareas: BackgroundTasks) -> Response:
        from twilio.request_validator import RequestValidator

        formulario = await request.form()
        datos = {k: str(v) for k, v in formulario.items()}  # todos los campos: la firma los incluye
        firma = request.headers.get("x-twilio-signature", "")
        if not token() or not RequestValidator(token()).validate(url_publica(request), datos, firma):
            log.warning("firma inválida")
            return Response("Firma inválida", status_code=403)

        vacio = Response(TWIML_VACIO, media_type="text/xml")
        sid, de, texto = datos.get("MessageSid", ""), datos.get("From", ""), datos.get("Body", "").strip()
        if not sid or not de.startswith("whatsapp:") or not texto:
            log.info("ignorado sid=%s motivo=sin texto o no es WhatsApp", sid or "-")
            return vacio
        if not recordados.primera_vez(sid):
            log.info("ignorado sid=%s motivo=repetido", sid)
            return vacio
        if not (modo_forzado() or fuera_de_horario(reloj(), APERTURA, CIERRE)):
            log.info("ignorado sid=%s motivo=dentro del horario", sid)
            return vacio
        tareas.add_task(responder, sid, texto, de)
        return vacio

    return app


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
app = crear_app()
