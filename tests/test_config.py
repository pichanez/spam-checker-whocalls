from importlib import util
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CONFIG_PATH = Path(__file__).resolve().parents[1] / "phone_spam_checker" / "config.py"
def load_config():
    spec = util.spec_from_file_location("config", CONFIG_PATH)
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore
    return module

config = load_config()


def test_settings_env(monkeypatch):
    monkeypatch.setenv("API_KEY", "abc")
    monkeypatch.setenv("KASP_ADB_HOST", "host")
    monkeypatch.setenv("KASP_ADB_PORT", "1111")
    global config
    config = load_config()
    assert config.settings.api_key == "abc"
    assert config.settings.kasp_adb_host == "host"
    assert config.settings.kasp_adb_port == "1111"
