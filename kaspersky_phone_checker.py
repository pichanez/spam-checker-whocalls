#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Проверка телефонных номеров через приложение Kaspersky Who Calls
с помощью uiautomator2 и «умными» ожиданиями (без time.sleep).
"""

import argparse
import csv
import logging
from dataclasses import dataclass, asdict
from pathlib import Path

import uiautomator2 as u2

# Пакет и активити приложения
APP_PACKAGE  = "com.kaspersky.who_calls"
APP_ACTIVITY = "com.kaspersky.who_calls.LauncherActivityAlias"

# Локаторы элементов
LOC_BTN_CHECK_NUMBER   = {'description': 'Check number'}
LOC_INPUT_FIELD        = {'className': 'android.widget.EditText'}
LOC_BTN_DO_CHECK       = {'text': 'Check'}
LOC_NO_FEEDBACK_TEXT   = {'text': 'No feedback on the number'}
LOC_BTN_CANCEL         = {'resourceId': 'android:id/button2'}
LOC_SPAM_TEXT          = {'textContains': 'SPAM!'}
LOC_USEFUL_TEXT        = {'textContains': 'useful'}

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

class KasperskyWhoCallsChecker:
    def __init__(self, device: str):
        """
        device — ID Android-устройства, например "127.0.0.1:5555" или серийник.
        """
        logger.info(f"Подключение к устройству {device}")
        self.d = u2.connect(device)
        # Включаем экран и разблокируем (если методы есть)
        for fn in ("screen_on", "unlock"):
            try:
                getattr(self.d, fn)()
            except Exception:
                pass

    def launch_app(self) -> bool:
        """
        Запустить приложение и нажать «Check number».
        """
        logger.info("Запуск приложения")
        try:
            self.d.app_start(APP_PACKAGE, activity=APP_ACTIVITY)
        except Exception as e:
            logger.error(f"Не удалось запустить приложение: {e}")
            return False

        btn = self.d(**LOC_BTN_CHECK_NUMBER)
        if not btn.wait(timeout=10):
            logger.error("Кнопка «Check number» не появилась")
            return False
        btn.click()

        if not self.d(**LOC_INPUT_FIELD).wait(timeout=8):
            logger.error("Поле ввода не появилось после «Check number»")
            return False
        return True

    def close_app(self) -> None:
        """
        Принудительно закрыть приложение.
        """
        logger.info("Закрытие приложения")
        self.d.app_stop(APP_PACKAGE)

    def check_number(self, phone: str) -> PhoneCheckResult:
        """
        Ввести номер, проверить и вернуть результат.
        """
        logger.info(f"Проверка номера: {phone}")
        result = PhoneCheckResult(phone_number=phone, status="Unknown")

        try:
            inp = self.d(**LOC_INPUT_FIELD)
            if not inp.wait(timeout=5):
                raise RuntimeError("Поле ввода не появилось")
            inp.click()
            inp.clear_text()
            inp.set_text(phone)

            btn_check = self.d(**LOC_BTN_DO_CHECK)
            if not btn_check.wait(timeout=5):
                raise RuntimeError("Кнопка «Check» не появилась")
            btn_check.click()

            # 1) Обработка «No feedback» попапа
            if self.d(**LOC_NO_FEEDBACK_TEXT).exists(timeout=4):
                logger.info("Номер не найден — закрываю попап")
                cancel = self.d(**LOC_BTN_CANCEL)
                if cancel.wait(timeout=3):
                    cancel.click()
                result.status = "Not in database"
            else:
                # 2) Результат найден — проверяем текст
                if self.d(**LOC_SPAM_TEXT).exists(timeout=4):
                    result.status = "Spam"
                elif self.d(**LOC_USEFUL_TEXT).exists(timeout=4):
                    result.status = "Safe"
                else:
                    result.status = "Unknown"

            # 3) Закрываем информационный попап (если был) и возвращаемся к вводу
            self.d.press("back")
            if not inp.wait(timeout=5):
                # если поле ввода не появилось — делаем второй back
                self.d.press("back")
                inp.wait(timeout=5)

        except Exception as e:
            logger.error(f"Ошибка при проверке {phone}: {e}")
            result.status = "Error"
            result.details = str(e)

        logger.info(f"{phone} → {result.status}")
        return result

def read_phone_list(path: Path) -> list[str]:
    """
    Считать номера из файла (один номер в строке).
    """
    return [line.strip() for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]

def write_results(path: Path, results: list[PhoneCheckResult]) -> None:
    """
    Сохранить результаты в CSV-файл.
    """
    with path.open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['phone_number', 'status', 'details'])
        writer.writeheader()
        for r in results:
            writer.writerow(asdict(r))

def main() -> int:
    parser = argparse.ArgumentParser(description="Проверка телефонных номеров через Kaspersky Who Calls")
    parser.add_argument('-i', '--input',  type=Path, required=True,  help="Файл со списком номеров")
    parser.add_argument('-o', '--output', type=Path, default=Path('results.csv'), help="Куда сохранить результаты")
    parser.add_argument('-d', '--device', type=str, default='127.0.0.1:5555', help="ID Android-устройства")
    args = parser.parse_args()

    if not args.input.exists():
        logger.error(f"Входной файл не найден: {args.input}")
        return 1

    phones = read_phone_list(args.input)
    logger.info(f"Загружено {len(phones)} номеров из {args.input}")

    checker = KasperskyWhoCallsChecker(args.device)
    if not checker.launch_app():
        return 1

    results = [checker.check_number(num) for num in phones]

    checker.close_app()
    write_results(args.output, results)
    logger.info(f"Результаты сохранены в {args.output}")
    return 0

if __name__ == '__main__':
    exit(main())