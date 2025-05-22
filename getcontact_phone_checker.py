#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Проверка телефонных номеров через приложение GetContact
с помощью uiautomator2 и «умных» ожиданий (без time.sleep).
"""

import argparse
import csv
import logging
from dataclasses import dataclass, asdict
from pathlib import Path

import uiautomator2 as u2


# ──────────────────────────────────────────────────────────────────────────────
#  Настройки приложения и локаторы UI
# ──────────────────────────────────────────────────────────────────────────────
APP_PACKAGE   = "app.source.getcontact"
APP_ACTIVITY  = ".ui.starter.StarterActivity"     # найдено через dumpsys

# Главный поиск
LOC_SEARCH_HINT  = {'resourceId': 'view.newsfeed.search.unfocus.searchhint'}    # "Search by number"
LOC_INPUT_FIELD  = {'resourceId': 'view.newsfeed.search.focus.searchfield'}     # EditText

# Результаты
LOC_NOT_FOUND    = {'resourceId': 'view.numberdetail.profile.notFoundDisplayNameText'}
LOC_NAME_TEXT    = {'resourceId': 'view.numberdetail.profile.displayNameText'}
LOC_SPAM_TEXT    = {'textContains': 'Spam'}

# Диалоги
LOC_LIMIT_DIALOG_CANCEL = {
    'resourceId': 'ConfirmationDialogNegativeButton',
    'text':       'CANCEL'
}
LOC_PRIVATE_MODE = {
    'resourceId': 'dialog.privateModeSettings.title'
}  # заголовок "Private Mode Settings"

# ──────────────────────────────────────────────────────────────────────────────
#  Логирование
# ──────────────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level   = logging.INFO,
    format  = "%(asctime)s %(levelname)s %(message)s",
    datefmt = "%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)


@dataclass
class PhoneCheckResult:
    phone_number: str
    status: str
    details: str = ""


class GetContactChecker:
    """Управляет приложением GetContact на подключённом Android-устройстве."""

    def __init__(self, device: str):
        logger.info(f"Connecting to device {device}")
        self.d = u2.connect(device)
        for fn in ("screen_on", "unlock"):
            try:
                getattr(self.d, fn)()
            except Exception:
                pass

    # ──────────────────────────────────────────────────────────────────────
    #  Запуск / остановка приложения
    # ──────────────────────────────────────────────────────────────────────
    def launch_app(self) -> bool:
        """Стартует GetContact и открывает строку поиска."""
        logger.info("Launching GetContact")
        try:
            self.d.app_start(APP_PACKAGE, activity=APP_ACTIVITY)
        except Exception as e:
            logger.error(f"Failed to launch GetContact: {e}")
            return False

        if not self.d(**LOC_SEARCH_HINT).wait(timeout=8):
            logger.error("Search hint did not appear")
            return False

        self.d(**LOC_SEARCH_HINT).click()
        if not self.d(**LOC_INPUT_FIELD).wait(timeout=3):
            logger.error("Input field did not appear after clicking search hint")
            return False
        return True

    def close_app(self) -> None:
        logger.info("Closing GetContact")
        self.d.app_stop(APP_PACKAGE)

    # ──────────────────────────────────────────────────────────────────────
    #  Проверка одного номера
    # ──────────────────────────────────────────────────────────────────────
    def check_number(self, phone: str) -> PhoneCheckResult:
        """Проверяет номер и возвращает результат."""
        if not phone.startswith("+"):
            phone = f"+{phone}"

        logger.info(f"Checking number: {phone}")
        result = PhoneCheckResult(phone_number=phone, status="Unknown")

        try:
            inp = self.d(**LOC_INPUT_FIELD)
            if not inp.wait(timeout=5):
                raise RuntimeError("Input field not available")

            # ввод номера
            inp.click()
            inp.clear_text()
            inp.set_text(phone)
            self.d.press("enter")

            # ── всплывающие окна ─────────────────────────────────────────
            if self.d(**LOC_LIMIT_DIALOG_CANCEL).exists(timeout=2):
                logger.info("Limit dialog detected → pressing CANCEL")
                self.d(**LOC_LIMIT_DIALOG_CANCEL).click()

            if self.d(**LOC_PRIVATE_MODE).exists(timeout=1):
                logger.info("Private-mode dialog detected → pressing BACK")
                self.d.press("back")

            # ── ждём появления любого валидного результата ───────────────
            cond_found = (
                self.d(**LOC_NOT_FOUND).wait(timeout=8) or
                self.d(**LOC_NAME_TEXT).exists or
                self.d(**LOC_SPAM_TEXT).exists
            )
            if not cond_found:
                raise RuntimeError("Result screen did not load")

            # ── интерпретация результата ─────────────────────────────────
            if self.d(**LOC_NOT_FOUND).exists:
                result.status  = "Not in database"
                result.details = "No result found!"
            elif self.d(**LOC_SPAM_TEXT).exists:
                result.status  = "Spam"
                result.details = self.d(**LOC_SPAM_TEXT).get_text()
            else:
                name = self.d(**LOC_NAME_TEXT).get_text()
                result.status  = "Safe"
                result.details = name

            # обратно к полю ввода
            self.d.press("back")
            inp.wait(timeout=3)

        except Exception as e:
            logger.error(f"Error checking {phone}: {e}")
            result.status  = "Error"
            result.details = str(e)

        logger.info(f"{phone} → {result.status}")
        return result


# ──────────────────────────────────────────────────────────────────────────────
#  Вспомогательные функции
# ──────────────────────────────────────────────────────────────────────────────
def read_phone_list(path: Path) -> list[str]:
    return [
        line.strip()
        for line in path.read_text(encoding='utf-8').splitlines()
        if line.strip()
    ]


def write_results(path: Path, results: list[PhoneCheckResult]) -> None:
    with path.open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['phone_number', 'status', 'details'])
        writer.writeheader()
        for r in results:
            writer.writerow(asdict(r))


# ──────────────────────────────────────────────────────────────────────────────
#  CLI-обёртка
# ──────────────────────────────────────────────────────────────────────────────
def main() -> int:
    parser = argparse.ArgumentParser(description="Проверка телефонных номеров через GetContact")
    parser.add_argument('-i', '--input',  type=Path, required=True,
                        help="Файл со списком номеров (по одному в строке)")
    parser.add_argument('-o', '--output', type=Path, default=Path('results_getcontact.csv'),
                        help="CSV-файл для сохранения результатов")
    parser.add_argument('-d', '--device', type=str, default='127.0.0.1:5555',
                        help="ID Android-устройства (adb connect)")
    args = parser.parse_args()

    if not args.input.exists():
        logger.error(f"Input file not found: {args.input}")
        return 1

    phones = read_phone_list(args.input)
    logger.info(f"Loaded {len(phones)} numbers from {args.input}")

    checker = GetContactChecker(args.device)
    if not checker.launch_app():
        return 1

    results = [checker.check_number(num) for num in phones]
    checker.close_app()
    write_results(args.output, results)
    logger.info(f"Results saved to {args.output}")
    return 0


if __name__ == '__main__':
    exit(main())