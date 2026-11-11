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

import hmac
import json
import logging
import os
import sys
import threading
import urllib.request
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


LIMITE_TELEGRAM = 4096


def dividir_mensaje(texto: str, limite: int = LIMITE_TELEGRAM) -> list[str]:
    """Parte el texto en trozos de hasta `limite` caracteres, cortando por párrafos (y si un párrafo
    no cabe, por líneas y, en último caso, a la fuerza)."""
    trozos: list[str] = []
    actual = ""
    for parrafo in texto.split("\n\n"):
        while len(parrafo) > limite:  # párrafo gigante: por línea o por corte duro
            corte = parrafo.rfind("\n", 0, limite)
            corte = corte if corte > 0 else limite
            if actual:
                trozos.append(actual)
                actual = ""
            trozos.append(parrafo[:corte])
            parrafo = parrafo[corte:].lstrip("\n")
        candidato = f"{actual}\n\n{parrafo}" if actual else parrafo
        if len(candidato) <= limite:
            actual = candidato
        else:
            trozos.append(actual)
            actual = parrafo
    if actual.strip():
        trozos.append(actual)
    return [t for t in trozos if t.strip()]


def _post_json(url: str, datos: dict) -> dict:
    peticion = urllib.request.Request(url, data=json.dumps(datos).encode("utf-8"),
                                      headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(peticion, timeout=15) as respuesta:  # noqa: S310 - URL fija de Telegram
        return json.loads(respuesta.read().decode("utf-8"))


class EnviadorTelegram:
    """Envía con sendMessage de la Bot API (biblioteca estándar). `post` se puede reemplazar en pruebas."""

    def __init__(self, bot_token: str | None = None, post: Callable[[str, dict], dict] = _post_json):
        self.bot_token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN", "")
        self._post = post

    def enviar(self, para: str, texto: str) -> str:
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        n = 0
        for trozo in dividir_mensaje(texto):
            self._post(url, {"chat_id": para, "text": trozo})
            n += 1
        return f"{n} trozo(s)"


def telegram_configurado() -> bool:
    return bool(os.getenv("TELEGRAM_BOT_TOKEN") and os.getenv("TELEGRAM_WEBHOOK_SECRET"))


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
              auth_token: str | None = None, tarifario=None,
              enviador_telegram: Enviador | None = None) -> FastAPI:
    """Las dependencias se pueden reemplazar en las pruebas (modelo, envío, reloj)."""
    app = FastAPI(title="Abra Travel: modo nocturno", docs_url=None, redoc_url=None)
    recordados = Recordados()
    estado = {"llm": llm, "enviador": enviador, "tarifario": tarifario, "telegram": enviador_telegram}

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

    def enviar_telegram(para: str, texto: str) -> str:
        if estado["telegram"] is None:
            estado["telegram"] = EnviadorTelegram()
        return estado["telegram"].enviar(para, texto)

    def responder(sid: str, texto: str, para: str, envio: Callable[[str, str], str] | None = None) -> None:
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
            enviado = (envio or enviar)(para, mensaje)
            log.info("respondido sid=%s %s envio=%s", sid, resumen, enviado)
        except Exception as error:  # noqa: BLE001
            log.error("no se pudo enviar sid=%s %s error=%s", sid, resumen, type(error).__name__)

    @app.get("/salud")
    def salud() -> dict:
        return {
            "estado": "ok",
            "horario_lima": f"{APERTURA:%H:%M}-{CIERRE:%H:%M}",
            "modo_forzado": modo_forzado(),
            "telegram_configurado": telegram_configurado(),
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

    @app.post("/telegram")
    async def telegram(request: Request, tareas: BackgroundTasks) -> Response:
        if not telegram_configurado():
            log.error("telegram sin configurar")
            return Response("Telegram no está configurado: faltan TELEGRAM_BOT_TOKEN o TELEGRAM_WEBHOOK_SECRET",
                            status_code=503)
        recibido = request.headers.get("x-telegram-bot-api-secret-token", "")
        if not hmac.compare_digest(recibido.encode(), os.getenv("TELEGRAM_WEBHOOK_SECRET", "").encode()):
            log.warning("telegram: secreto inválido")
            return Response("Secreto inválido", status_code=403)
        try:
            update = await request.json()
            mensaje = update.get("message") or {}
            uid = update.get("update_id")
            chat = (mensaje.get("chat") or {}).get("id")
            texto = mensaje.get("text")
            texto = texto.strip() if isinstance(texto, str) else ""
        except (ValueError, AttributeError):
            return Response(status_code=200)
        if chat is None or not texto:
            log.info("telegram ignorado update=%s motivo=sin texto", uid)
            return Response(status_code=200)
        clave = f"tg{uid if uid is not None else chat}-{mensaje.get('message_id', '')}"
        if not recordados.primera_vez(clave):
            log.info("telegram ignorado %s motivo=repetido", clave)
            return Response(status_code=200)
        if not (modo_forzado() or fuera_de_horario(reloj(), APERTURA, CIERRE)):
            log.info("telegram ignorado %s motivo=dentro del horario", clave)
            return Response(status_code=200)
        tareas.add_task(responder, clave, texto, str(chat), enviar_telegram)
        return Response(status_code=200)

    return app


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
app = crear_app()
