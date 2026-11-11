"""Pruebas del endpoint POST /telegram. Sin red: el envío (sendMessage) se simula."""
import os
import sys
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

try:
    from fastapi.testclient import TestClient
except ImportError as falta:  # pragma: no cover
    raise unittest.SkipTest(f"Falta {falta.name}")

from ai.fecha import ZONA  # noqa: E402
from server.webhook import EnviadorTelegram, crear_app, dividir_mensaje  # noqa: E402
from tests.test_webhook import ModeloSimulado, TEXTO  # noqa: E402

SECRETO, BOT = "secreto_de_prueba", "bot_de_prueba"
CABECERA = {"X-Telegram-Bot-Api-Secret-Token": SECRETO}


def update(texto=TEXTO, chat=777, uid=1):
    mensaje = {"message_id": 5, "chat": {"id": chat, "type": "private"}}
    if texto is not None:
        mensaje["text"] = texto
    return {"update_id": uid, "message": mensaje}


class Base(unittest.TestCase):
    env = {"TELEGRAM_BOT_TOKEN": BOT, "TELEGRAM_WEBHOOK_SECRET": SECRETO, "FORZAR_MODO_NOCTURNO": ""}

    def setUp(self):
        self.entorno = mock.patch.dict(os.environ, self.env)
        self.entorno.start()
        self.llamadas = []
        self.enviador = EnviadorTelegram(post=lambda url, datos: self.llamadas.append((url, datos)) or {"ok": True})
        self.modelo = ModeloSimulado()
        self.cliente = TestClient(crear_app(llm=self.modelo, enviador_telegram=self.enviador,
                                            reloj=lambda: datetime(2026, 11, 10, 0, 7, tzinfo=ZONA)))

    def tearDown(self):
        self.entorno.stop()


class PruebasTelegram(Base):
    def test_sin_secreto_403(self):
        self.assertEqual(self.cliente.post("/telegram", json=update()).status_code, 403)
        self.assertEqual(self.cliente.post("/telegram", json=update(),
                                           headers={"X-Telegram-Bot-Api-Secret-Token": "otro"}).status_code, 403)
        self.assertEqual(self.llamadas, [])

    def test_mensaje_normal_envia_al_chat(self):
        r = self.cliente.post("/telegram", json=update(), headers=CABECERA)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(self.llamadas), 1)
        url, datos = self.llamadas[0]
        self.assertEqual(url, f"https://api.telegram.org/bot{BOT}/sendMessage")
        self.assertEqual(datos["chat_id"], "777")
        self.assertTrue(datos["text"].strip())

    def test_sin_texto_se_ignora(self):
        r = self.cliente.post("/telegram", json=update(texto=None), headers=CABECERA)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.llamadas, [])
        self.assertEqual(self.modelo.llamadas, [])

    def test_repetido_no_responde_dos_veces(self):
        for _ in range(2):
            self.cliente.post("/telegram", json=update(), headers=CABECERA)
        self.assertEqual(len(self.llamadas), 1)

    def test_no_registra_el_texto_ni_el_token(self):
        with self.assertLogs("abra.webhook", level="INFO") as registro:
            self.cliente.post("/telegram", json=update(), headers=CABECERA)
        salida = "\n".join(registro.output)
        self.assertNotIn(TEXTO[:30], salida)
        self.assertNotIn(BOT, salida)


class PruebasSinConfigurar(Base):
    env = {"TELEGRAM_BOT_TOKEN": "", "TELEGRAM_WEBHOOK_SECRET": ""}

    def test_503_y_salud_false(self):
        r = self.cliente.post("/telegram", json=update(), headers=CABECERA)
        self.assertEqual(r.status_code, 503)
        self.assertIn("TELEGRAM_BOT_TOKEN", r.text)
        self.assertIs(self.cliente.get("/salud").json()["telegram_configurado"], False)


class PruebasSalud(Base):
    def test_salud_true(self):
        self.assertIs(self.cliente.get("/salud").json()["telegram_configurado"], True)


class PruebasDividir(unittest.TestCase):
    def test_corta_por_parrafos(self):
        texto = "\n\n".join(["a" * 1500] * 5)
        trozos = dividir_mensaje(texto)
        self.assertTrue(all(len(t) <= 4096 for t in trozos))
        self.assertEqual(len(trozos), 3)
        self.assertEqual("\n\n".join(trozos), texto)

    def test_parrafo_gigante(self):
        self.assertTrue(all(len(t) <= 4096 for t in dividir_mensaje("x" * 10000)))


if __name__ == "__main__":
    unittest.main()
