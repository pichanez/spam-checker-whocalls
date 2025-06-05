import sys
import types
sys.modules.setdefault("uiautomator2", types.ModuleType("uiautomator2"))
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import phone_checker_cli


def test_cli_dispatch(monkeypatch):
    called = {}

    def fake_main():
        called["service"] = True
        return 123

    monkeypatch.setitem(phone_checker_cli.SERVICES, "kaspersky", fake_main)
    assert phone_checker_cli.main(["kaspersky"]) == 123
    assert called["service"]


