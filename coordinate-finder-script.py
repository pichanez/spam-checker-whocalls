#!/usr/bin/env python3
"""
Скрипт для получения скриншота и определения координат элементов интерфейса.
"""

import subprocess
import os
import time
import argparse

def run_adb_command(device_id, command):
    """
    Выполнить команду ADB на устройстве.
    
    Args:
        device_id (str): ID устройства
        command (str): Команда ADB без префикса 'adb -s device_id'
        
    Returns:
        str: Вывод команды или None в случае ошибки
    """
    full_command = f"adb -s {device_id} {command}"
    print(f"Выполнение команды: {full_command}")
    
    try:
        result = subprocess.run(
            full_command, 
            shell=True, 
            check=True, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            text=True
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"Ошибка при выполнении команды ADB: {e}")
        print(f"STDERR: {e.stderr}")
        return None

def capture_screenshot(device_id, output_path="screen.png"):
    """
    Сделать скриншот экрана устройства и сохранить его на компьютере.
    
    Args:
        device_id (str): ID устройства
        output_path (str): Путь для сохранения скриншота
        
    Returns:
        bool: True если скриншот сделан успешно, иначе False
    """
    # Проверяем, какие директории доступны для записи
    print("Проверка доступных директорий...")
    directories = ["/data/local/tmp", "/data", "/tmp", "/storage/emulated/0"]
    
    for directory in directories:
        check_cmd = f"shell '[ -w \"{directory}\" ] && echo \"writable\" || echo \"not writable\"'"
        result = run_adb_command(device_id, check_cmd)
        print(f"Директория {directory}: {result.strip() if result else 'ошибка проверки'}")
    
    # Попробуем использовать /data/local/tmp вместо /sdcard
    remote_path = "/data/local/tmp/screen.png"
    
    # Сделать скриншот и сохранить его на устройстве
    screenshot_cmd = f"shell screencap -p {remote_path}"
    if run_adb_command(device_id, screenshot_cmd) is None:
        return False
    
    # Скопировать скриншот с устройства на компьютер
    pull_cmd = f"pull {remote_path} {output_path}"
    if run_adb_command(device_id, pull_cmd) is None:
        return False
    
    print(f"Скриншот сохранен в {output_path}")
    return True

def get_ui_dump(device_id, output_path="ui_dump.xml"):
    """
    Получить XML-дамп интерфейса устройства и сохранить его на компьютере.
    
    Args:
        device_id (str): ID устройства
        output_path (str): Путь для сохранения XML-дампа
        
    Returns:
        bool: True если дамп получен успешно, иначе False
    """
    # Используем /data/local/tmp вместо /sdcard
    remote_path = "/data/local/tmp/ui_dump.xml"
    
    # Запустить uiautomator dump на устройстве
    dump_cmd = f"shell uiautomator dump {remote_path}"
    if run_adb_command(device_id, dump_cmd) is None:
        return False
    
    # Скопировать XML-дамп с устройства на компьютер
    pull_cmd = f"pull {remote_path} {output_path}"
    if run_adb_command(device_id, pull_cmd) is None:
        return False
    
    print(f"UI-дамп сохранен в {output_path}")
    return True

def launch_app(device_id, package_name, activity_name):
    """
    Запустить приложение на устройстве.
    
    Args:
        device_id (str): ID устройства
        package_name (str): Имя пакета приложения
        activity_name (str): Имя активности
        
    Returns:
        bool: True если приложение запущено успешно, иначе False
    """
    launch_cmd = f"shell am start -n {package_name}/{activity_name}"
    result = run_adb_command(device_id, launch_cmd)
    
    if result and "Error" not in result:
        print("Приложение запущено успешно")
        time.sleep(2)  # Даем приложению время на загрузку
        return True
    else:
        print("Не удалось запустить приложение")
        return False

def main():
    """Основная функция для запуска скрипта"""
    parser = argparse.ArgumentParser(description='Получение скриншота и UI-дампа для определения координат')
    parser.add_argument('--device', '-d', default='127.0.0.1:5555', help='ID устройства в формате IP:порт')
    parser.add_argument('--launch', '-l', action='store_true', help='Запустить приложение перед получением данных')
    
    args = parser.parse_args()
    
    if args.launch:
        package_name = "com.kaspersky.who_calls"
        activity_name = ".LauncherActivityAlias"
        launch_app(args.device, package_name, activity_name)
    
    # Получение скриншота
    timestamp = int(time.time())
    screenshot_path = f"screen_{timestamp}.png"
    if not capture_screenshot(args.device, screenshot_path):
        print("Не удалось получить скриншот")
    
    # Получение UI-дампа
    ui_dump_path = f"ui_dump_{timestamp}.xml"
    if not get_ui_dump(args.device, ui_dump_path):
        print("Не удалось получить UI-дамп")
    
    print("\nДля определения координат элементов:")
    print(f"1. Откройте скриншот {screenshot_path} в графическом редакторе")
    print("2. Наведите курсор на нужный элемент, чтобы увидеть его координаты")
    print(f"3. Откройте UI-дамп {ui_dump_path} в текстовом редакторе для получения дополнительной информации об элементах")
    
    return 0

if __name__ == "__main__":
    exit(main())