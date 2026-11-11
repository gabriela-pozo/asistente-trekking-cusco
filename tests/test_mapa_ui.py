import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

import mapa_ui  # noqa: E402


class PruebasMapaUI(unittest.TestCase):
    def test_mostrar_mapa_nunca_lanza(self):
        for trek in ("salkantay", "camino_inca", "lares", "choquequirao", None, "???"):
            mapa_ui.mostrar_mapa(trek)

    def test_trek_detectado(self):
        con = SimpleNamespace(perfil=SimpleNamespace(treks_de_interes=["lares", "salkantay"]))
        sin = SimpleNamespace(perfil=SimpleNamespace(treks_de_interes=[]))
        self.assertEqual(mapa_ui.trek_detectado(con), "lares")
        self.assertIsNone(mapa_ui.trek_detectado(sin))
        self.assertIsNone(mapa_ui.trek_detectado(None))

    def test_wrapper_no_lanza(self):
        mapa_ui.mostrar_mapa_del_resultado(None)
        mapa_ui.mostrar_mapa_del_resultado(SimpleNamespace(perfil=SimpleNamespace(treks_de_interes=["salkantay"])))


if __name__ == "__main__":
    unittest.main()
