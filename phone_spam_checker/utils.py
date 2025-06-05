import csv
from dataclasses import asdict
from pathlib import Path
from typing import Iterable

from .domain.models import PhoneCheckResult


def read_phone_list(path: Path) -> list[str]:
    """Read phone numbers from a text file."""
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_results(path: Path, results: Iterable[PhoneCheckResult]) -> None:
    """Write check results to CSV."""
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["phone_number", "status", "details"])
        writer.writeheader()
        for r in results:
            row = asdict(r)
            status = row.get("status")
            if hasattr(status, "value"):
                row["status"] = status.value
            writer.writerow(row)
