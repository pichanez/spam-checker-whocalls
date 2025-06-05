import sys
import types
import csv
from pathlib import Path

sys.modules.setdefault("uiautomator2", types.ModuleType("uiautomator2"))

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from phone_spam_checker.utils import read_phone_list, write_results  # noqa: E402
from phone_spam_checker.domain.models import PhoneCheckResult, CheckStatus  # noqa: E402


def test_read_phone_list(tmp_path: Path) -> None:
    file = tmp_path / "phones.txt"
    file.write_text("+123\n456\n", encoding="utf-8")
    assert read_phone_list(file) == ["+123", "456"]


def test_write_results(tmp_path: Path) -> None:
    file = tmp_path / "out.csv"
    results = [PhoneCheckResult(phone_number="123", status=CheckStatus.SPAM, details="bad")]
    write_results(file, results)
    with file.open(encoding="utf-8") as f:
        reader = list(csv.DictReader(f))
    assert reader == [{"phone_number": "123", "status": "Spam", "details": "bad"}]
