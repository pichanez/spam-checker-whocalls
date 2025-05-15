#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Проверка телефонных номеров через приложение Truecaller
с помощью uiautomator2 и «умными» ожиданиями (без time.sleep).
"""

import argparse
import csv
import logging
from dataclasses import dataclass, asdict
from pathlib import Path

import uiautomator2 as u2

# Пакет и активити Truecaller
APP_PACKAGE      = "com.truecaller"
APP_ACTIVITY     = "com.truecaller.ui.TruecallerInit"

# Локаторы
LOC_SEARCH_LABEL   = {'resourceId': 'com.truecaller:id/searchBarLabel'}   # полоса «Search numbers…»
LOC_INPUT_FIELD    = {'resourceId': 'com.truecaller:id/search_field'}     # AutoCompleteTextView для ввода номера
LOC_SEARCH_WEB     = {'resourceId': 'com.truecaller:id/searchWeb'}        # кнопка «SEARCH THE WEB» при отсутствии данных
LOC_SPAM_TEXT      = {'textContains': 'SPAM'}                            # метка спама в результате
LOC_NAME_OR_NUMBER = {'resourceId': 'com.truecaller:id/nameOrNumber'}     # имя или номер в заголовке
LOC_NUMBER_DETAILS = {'resourceId': 'com.truecaller:id/numberDetails'}    # детали номера (оператор, регион)
LOC_PHONE_NUMBER   = {'resourceId': 'com.truecaller:id/phoneNumber'}      # текст номера на экране результата

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

@dataclass
class PhoneCheckResult:
    phone_number: str
    status: str
    details: str = ""

class TruecallerChecker:
    def __init__(self, device: str):
        logger.info(f"Connecting to device {device}")
        self.d = u2.connect(device)
        for fn in ("screen_on", "unlock"):
            try:
                getattr(self.d, fn)()
            except Exception:
                pass

    def launch_app(self) -> bool:
        logger.info("Launching Truecaller")
        try:
            self.d.app_start(APP_PACKAGE, activity=APP_ACTIVITY)
        except Exception as e:
            logger.error(f"Failed to launch Truecaller: {e}")
            return False

        for btn_text in ("ALLOW", "Allow", "Разрешить", "ALLOW ALL THE TIME"):
            if self.d(text=btn_text).exists(timeout=2):
                logger.info(f"Clicking system dialog: {btn_text}")
                self.d(text=btn_text).click()

        lbl = self.d(**LOC_SEARCH_LABEL)
        if not lbl.wait(timeout=2):
            logger.error("Search label did not appear")
            return False
        lbl.click()

        if not self.d(**LOC_INPUT_FIELD).wait(timeout=2):
            logger.error("Input field did not appear after clicking search")
            return False
        return True

    def close_app(self) -> None:
        logger.info("Closing Truecaller")
        self.d.app_stop(APP_PACKAGE)

    def check_number(self, phone: str) -> PhoneCheckResult:
        logger.info(f"Checking number: {phone}")
        result = PhoneCheckResult(phone_number=phone, status="Unknown")

        try:
            inp = self.d(**LOC_INPUT_FIELD)
            if not inp.wait(timeout=5):
                raise RuntimeError("Input field not available")
            inp.click(); inp.clear_text(); inp.set_text(phone)
            self.d.press("enter")

            # Ждём результатов
            if not self.d(**LOC_PHONE_NUMBER).wait(timeout=5) and not self.d(**LOC_SPAM_TEXT).exists(timeout=5):
                raise RuntimeError("Result screen did not load")

            # Если есть кнопка Search in the web — номера нет в базе
            if self.d(**LOC_SEARCH_WEB).exists(timeout=2):
                logger.info("No entry in database — SEARCH THE WEB found")
                result.status = "Not in database"
            else:
                # Спам?
                if self.d(**LOC_SPAM_TEXT).exists(timeout=3):
                    result.status = "Spam"
                else:
                    # Безопасный номер — вытаскиваем имя/номер и детали
                    name_or_num = self.d(**LOC_NAME_OR_NUMBER).get_text()
                    details = ""
                    if self.d(**LOC_NUMBER_DETAILS).exists(timeout=2):
                        details = self.d(**LOC_NUMBER_DETAILS).get_text()
                    result.status = "Safe"
                    result.details = f"{name_or_num}; {details}" if details else name_or_num

            # Возвращаемся назад к вводу
            self.d.press("back")
            if not inp.wait(timeout=3):
                self.d.press("back"); inp.wait(timeout=5)

        except Exception as e:
            logger.error(f"Error checking {phone}: {e}")
            result.status = "Error"
            result.details = str(e)

        logger.info(f"{phone} → {result.status}")
        return result


def read_phone_list(path: Path) -> list[str]:
    return [line.strip() for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]


def write_results(path: Path, results: list[PhoneCheckResult]) -> None:
    with path.open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['phone_number','status','details'])
        writer.writeheader()
        for r in results:
            writer.writerow(asdict(r))


def main() -> int:
    parser = argparse.ArgumentParser(description="Проверка телефонных номеров через Truecaller")
    parser.add_argument('-i','--input', type=Path, required=True, help="Файл со списком номеров")
    parser.add_argument('-o','--output', type=Path, default=Path('results_truecaller.csv'), help="Куда сохранить результаты")
    parser.add_argument('-d','--device', type=str, default='127.0.0.1:5555', help="ID Android-устройства")
    args = parser.parse_args()

    if not args.input.exists():
        logger.error(f"Input file not found: {args.input}")
        return 1

    phones = read_phone_list(args.input)
    logger.info(f"Loaded {len(phones)} numbers from {args.input}")

    checker = TruecallerChecker(args.device)
    if not checker.launch_app():
        return 1

    results = [checker.check_number(num) for num in phones]
    checker.close_app()
    write_results(args.output, results)
    logger.info(f"Results saved to {args.output}")
    return 0

if __name__ == '__main__':
    exit(main())
