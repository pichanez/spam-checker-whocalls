#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Проверка телефонных номеров через приложение Kaspersky Who Calls с помощью ADB.

Этот скрипт автоматически запускает приложение на подключённом устройстве (эмуляторе или физическом Android),
вводит номер телефона, выполняет проверку и сохраняет результаты в CSV-файл.
"""

import argparse
import csv
import logging
import subprocess
import time
import re
from dataclasses import dataclass, asdict
from pathlib import Path

# Константы
APP_PACKAGE = "com.kaspersky.who_calls"
APP_ACTIVITY = "com.kaspersky.who_calls.LauncherActivityAlias"
ADB_TIMEOUT = 10  # таймаут для ADB-команд, сек
PAUSE_SHORT = 1.0  # короткая пауза между действиями, сек
PAUSE_LONG = 5.0   # пауза для ожидания загрузки, сек

# Координаты (X, Y) для взаимодействия с UI (примерные значения)
SEARCH_BUTTON = (270, 1128)
INPUT_FIELD = (360, 474)
CHECK_BUTTON = (360, 632)
CANCEL_BUTTON_FALLBACK = (200, 800)

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)


@dataclass
class PhoneCheckResult:
    phone_number: str
    status: str
    details: str = ""


class KasperskyWhoCallsChecker:
    """
    Проверка номеров через приложение Kaspersky Who Calls с помощью ADB.
    """

    def __init__(self, device_id: str):
        """
        Args:
            device_id (str): ID устройства (например, "127.0.0.1:5555").
        """
        self.device_id = device_id
        self.logger = logging.getLogger(self.__class__.__name__)

    def _adb(self, *args: str, timeout: int = ADB_TIMEOUT) -> str:
        """
        Выполнить ADB-команду и вернуть stdout.
        """
        cmd = ["adb", "-s", self.device_id, *args]
        self.logger.debug(f"ADB: {' '.join(cmd)}")
        try:
            return subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True, timeout=timeout)
        except subprocess.CalledProcessError as e:
            self.logger.error(f"ADB error: {e.output.strip()}")
            return ""
        except subprocess.TimeoutExpired:
            self.logger.error("ADB command timeout")
            return ""

    def launch_app(self) -> bool:
        """
        Запустить приложение.
        Returns:
            bool: True если успешно, иначе False.
        """
        self.logger.info("Запуск приложения")
        out = self._adb("shell", "am", "start", "-n", f"{APP_PACKAGE}/{APP_ACTIVITY}")
        if 'Error' in out:
            self.logger.error("Не удалось запустить приложение")
            return False
        time.sleep(PAUSE_LONG)
        return True

    def close_app(self) -> None:
        """
        Закрыть приложение принудительно.
        """
        self.logger.info("Закрытие приложения")
        self._adb("shell", "am", "force-stop", APP_PACKAGE)
        time.sleep(PAUSE_SHORT)

    def tap(self, coords: tuple[int, int], pause: float = PAUSE_SHORT) -> None:
        """
        Нажать на экран в указанных координатах.
        """
        x, y = coords
        self._adb("shell", "input", "tap", str(x), str(y))
        time.sleep(pause)

    def open_search(self) -> bool:
        """
        Перейти на экран проверки номера.
        Returns:
            bool: Всегда True (если нет критической ошибки).
        """
        self.logger.info("Переход на экран проверки")
        self.tap(SEARCH_BUTTON)
        return True

    def check_number(self, phone: str) -> PhoneCheckResult:
        """
        Проверить один номер телефона.

        Args:
            phone (str): Телефонный номер.

        Returns:
            PhoneCheckResult: Результат проверки.
        """
        result = PhoneCheckResult(phone_number=phone, status="Unknown")
        self.logger.info(f"Проверка номера: {phone}")

        try:
            # Клик в поле ввода и очистка
            self.tap(INPUT_FIELD)
            self._adb("shell", "input", "keyevent", "KEYCODE_MOVE_END")
            for _ in range(20):
                self._adb("shell", "input", "keyevent", "KEYCODE_DEL")

            # Ввод номера (кодируем '+' как '%2B')
            encoded = phone.replace('+', '%2B')
            self._adb("shell", "input", "text", encoded)
            time.sleep(PAUSE_SHORT)

            # Нажатие кнопки проверки и ожидание
            self.tap(CHECK_BUTTON, pause=PAUSE_LONG)

            # Создание дампа UI
            remote = "/data/local/tmp/result.xml"
            self._adb("shell", "uiautomator", "dump", remote)
            local_path = Path(f"dump_{phone.strip('+')}.xml")
            self._adb("pull", remote, str(local_path))

            # Чтение и анализ XML
            content = local_path.read_text(encoding='utf-8')
            lower = content.lower()

            # Проверка отсутствия данных
            if 'no feedback' in content:
                result.status = "Not in database"
                self._close_popup(content)
            else:
                if 'spam!' in lower or 'мошенник' in lower:
                    result.status = "Spam"
                elif 'useful' in lower or 'безопасный' in lower:
                    result.status = "Safe"
                else:
                    result.status = "Unknown"
                # Возврат назад
                self._adb("shell", "input", "keyevent", "KEYCODE_BACK")

            # Удаление временного файла
            local_path.unlink(missing_ok=True)

        except Exception as e:
            self.logger.error(f"Ошибка при проверке {phone}: {e}")
            result.status = "Error"
            result.details = str(e)

        self.logger.info(f"Результат: {result.status}")
        return result

    def _close_popup(self, xml: str) -> None:
        """
        Закрыть модальное окно 'No feedback'.
        """
        match = re.search(r'text="Cancel"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', xml)
        if match:
            x1, y1, x2, y2 = map(int, match.groups())
            self.tap(((x1 + x2) // 2, (y1 + y2) // 2))
        else:
            self.tap(CANCEL_BUTTON_FALLBACK)


def read_phone_list(path: Path) -> list[str]:
    """
    Прочитать список номеров из файла (один на строку).
    """
    return [line.strip() for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]


def write_results(path: Path, results: list[PhoneCheckResult]) -> None:
    """
    Сохранить результаты проверки в CSV.
    """
    with path.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['phone_number', 'status', 'details'])
        writer.writeheader()
        for res in results:
            writer.writerow(asdict(res))


def main() -> int:
    """
    Основная функция: парсинг аргументов и запуск проверки.
    """
    parser = argparse.ArgumentParser(
        description="Проверка телефонных номеров через Kaspersky Who Calls"
    )
    parser.add_argument('-i', '--input', type=Path, required=True, help="Входной файл с номерами")
    parser.add_argument('-o', '--output', type=Path, default=Path('results.csv'), help="Файл для сохранения результатов")
    parser.add_argument('-d', '--device', type=str, default='127.0.0.1:5555', help="ID Android-устройства")
    args = parser.parse_args()

    if not args.input.exists():
        logger.error(f"Входной файл не найден: {args.input}")
        return 1

    phones = read_phone_list(args.input)
    logger.info(f"Загружено {len(phones)} номеров из {args.input}")

    checker = KasperskyWhoCallsChecker(args.device)

    # Запускаем приложение один раз перед всеми проверками
    if not checker.launch_app():
        logger.error("Не удалось запустить приложение, прерывание проверки")
        return 1

    results = []
    for number in phones:
        checker.open_search()
        results.append(checker.check_number(number))

    # Закрываем приложение после всех проверок
    checker.close_app()

    write_results(args.output, results)
    logger.info(f"Результаты сохранены в {args.output}")
    return 0


if __name__ == '__main__':
    exit(main())
