import sys
import types
import csv
from pathlib import Path
import pytest

sys.modules.setdefault("uiautomator2", types.ModuleType("uiautomator2"))

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for path in (str(SRC), str(ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

from phone_spam_checker.logging_config import configure_logging
from phone_spam_checker.config import settings

configure_logging(
    level=settings.log_level,
    fmt=settings.log_format,
    log_file=settings.log_file,
)

from phone_spam_checker.utils import read_phone_list, write_results  # noqa: E402
from phone_spam_checker.domain.models import PhoneCheckResult, CheckStatus  # noqa: E402


def test_read_phone_list(tmp_path: Path) -> None:
    file = tmp_path / "phones.txt"
    file.write_text("+123\n456\n", encoding="utf-8")
    assert read_phone_list(file) == ["+123", "456"]


def test_read_phone_list_invalid(tmp_path: Path) -> None:
    file = tmp_path / "phones.txt"
    file.write_text("12a\n", encoding="utf-8")
    with pytest.raises(ValueError):
        read_phone_list(file)


def test_write_results(tmp_path: Path) -> None:
    file = tmp_path / "out.csv"
    results = [PhoneCheckResult(phone_number="123", status=CheckStatus.SPAM, details="bad")]
    write_results(file, results)
    with file.open(encoding="utf-8") as f:
        reader = list(csv.DictReader(f))
    assert reader == [{"phone_number": "123", "status": "Spam", "details": "bad"}]
