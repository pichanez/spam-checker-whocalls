import sys
import types

sys.modules.setdefault("uiautomator2", types.ModuleType("uiautomator2"))
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from phone_spam_checker.logging_config import configure_logging
from phone_spam_checker.config import settings

configure_logging(
    level=settings.log_level,
    fmt=settings.log_format,
    log_file=settings.log_file,
)

from scripts import phone_checker_cli
from phone_spam_checker import cli_base


def test_cli_dispatch(monkeypatch):
    called = {}

    def fake_run(service, argv=None):
        called["service"] = service
        called["argv"] = argv
        return 123

    monkeypatch.setattr(cli_base, "run_checker", fake_run)
    monkeypatch.setattr(phone_checker_cli, "run_checker", fake_run)
    assert phone_checker_cli.main(["kaspersky", "-i", "f.txt"]) == 123
    assert called == {"service": "kaspersky", "argv": ["-i", "f.txt"]}
