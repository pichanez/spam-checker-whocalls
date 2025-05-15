# Используем лёгкий образ с Python 3.10
FROM python:3.10-slim

# Устанавливаем ADB для взаимодействия с Android-устройством
RUN apt-get update \
    && apt-get install -y --no-install-recommends android-tools-adb \
    && rm -rf /var/lib/apt/lists/*

# Рабочая директория
WORKDIR /app

# Копируем и устанавливаем Python-зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь код проекта
COPY . .

# Создаём entrypoint-скрипт внутри контейнера без CRLF
RUN printf '#!/bin/sh\n' > /entrypoint.sh \
    && printf 'adb connect ${KASP_ADB_HOST}:${KASP_ADB_PORT}\n' >> /entrypoint.sh \
    && printf 'adb connect ${TC_ADB_HOST}:${TC_ADB_PORT}\n' >> /entrypoint.sh \
    && printf 'exec uvicorn api:app --host 0.0.0.0 --port 8000\n' >> /entrypoint.sh \
    && chmod +x /entrypoint.sh

# Открываем порт для FastAPI
EXPOSE 8000

# Используем entrypoint для старта приложения
ENTRYPOINT ["/entrypoint.sh"]