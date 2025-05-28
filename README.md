# Phone Spam Checker

Сервис для проверки телефонных номеров на принадлежность к спам-звонкам с использованием мобильных приложений Kaspersky Who Calls, Truecaller и GetContact.

## Особенности

- Проверка номеров через популярные мобильные приложения
- Асинхронная обработка запросов
- Кэширование результатов для быстрого доступа
- API с аутентификацией по ключу
- Ограничение количества запросов (Rate Limiting)
- Мониторинг и аудит действий
- Контейнеризация с Docker и Docker Compose
- CI/CD с GitHub Actions

## Архитектура

Проект построен на основе многослойной архитектуры:

```
app/
├── api/              # API-слой (контроллеры, модели)
├── services/         # Сервисный слой (бизнес-логика)
├── repositories/     # Репозитории (доступ к данным)
├── infrastructure/   # Инфраструктурные компоненты
│   ├── device/       # Работа с устройствами
│   └── checkers/     # Стратегии проверки номеров
└── utils/            # Утилиты и вспомогательные функции
```

### Ключевые компоненты

- **FastAPI** - для создания REST API
- **Redis** - для кэширования результатов
- **uiautomator2** - для взаимодействия с Android-устройствами
- **Prometheus** - для сбора метрик
- **Docker** - для контейнеризации

## Требования

- Python 3.11+
- Redis
- Android-устройства с установленными приложениями:
  - Kaspersky Who Calls
  - Truecaller
  - GetContact

## Установка и запуск

### Локальный запуск

1. Клонировать репозиторий:
   ```bash
   git clone https://github.com/pichanez/phone-spam-checker.git
   cd phone-spam-checker
   ```

2. Установить зависимости:
   ```bash
   pip install -r requirements.txt
   ```

3. Настроить переменные окружения:
   ```bash
   export REDIS_URL="redis://localhost:6379/0"
   export API_KEY="your_secure_api_key"
   export KASP_ADB_HOST="127.0.0.1"
   export KASP_ADB_PORT="5555"
   export TC_ADB_HOST="127.0.0.1"
   export TC_ADB_PORT="5556"
   export GC_ADB_HOST="127.0.0.1"
   export GC_ADB_PORT="5557"
   ```

4. Запустить Redis:
   ```bash
   docker run -d -p 6379:6379 redis:6
   ```

5. Запустить приложение:
   ```bash
   python -m app.main
   ```

### Запуск с Docker Compose

1. Клонировать репозиторий:
   ```bash
   git clone https://github.com/pichanez/phone-spam-checker.git
   cd phone-spam-checker
   ```

2. Создать файл `.env` с переменными окружения:
   ```
   API_KEY=your_secure_api_key
   REDIS_URL=redis://redis:6379/0
   KASP_ADB_HOST=kaspersky-device
   KASP_ADB_PORT=5555
   TC_ADB_HOST=truecaller-device
   TC_ADB_PORT=5555
   GC_ADB_HOST=getcontact-device
   GC_ADB_PORT=5555
   ```

3. Запустить с Docker Compose:
   ```bash
   docker-compose up -d
   ```

## Использование API

### Проверка номеров

```bash
curl -X POST "http://localhost:8000/check_numbers" \
  -H "X-API-Key: your_api_key" \
  -H "Content-Type: application/json" \
  -d '{"numbers": ["+79123456789", "+12025550108"], "use_cache": true}'
```

Ответ:
```json
{
  "job_id": "a1b2c3d4e5f6"
}
```

### Получение результатов

```bash
curl -X GET "http://localhost:8000/status/a1b2c3d4e5f6" \
  -H "X-API-Key: your_api_key"
```

Ответ:
```json
{
  "job_id": "a1b2c3d4e5f6",
  "status": "completed",
  "results": [
    {
      "phone_number": "+79123456789",
      "status": "Safe",
      "details": "Иванов Иван - Мобильный",
      "source": "kaspersky"
    },
    {
      "phone_number": "+12025550108",
      "status": "Spam",
      "details": "Spam Call - Telemarketing",
      "source": "truecaller"
    }
  ],
  "progress": 100.0
}
```

### Проверка состояния устройств

```bash
curl -X GET "http://localhost:8000/device_status" \
  -H "X-API-Key: your_api_key"
```

### Очистка кэша

```bash
curl -X POST "http://localhost:8000/cache/clear" \
  -H "X-API-Key: your_api_key"
```

### Статистика кэша

```bash
curl -X GET "http://localhost:8000/cache/stats" \
  -H "X-API-Key: your_api_key"
```

### Проверка работоспособности

```bash
curl -X GET "http://localhost:8000/health"
```

## Тестирование

### Запуск модульных тестов

```bash
pytest tests/unit/
```

### Запуск интеграционных тестов

```bash
pytest tests/integration/
```

### Запуск всех тестов с отчетом о покрытии

```bash
pytest --cov=app tests/
```

## Безопасность

- Аутентификация по API-ключу
- Ограничение количества запросов (Rate Limiting)
- Аудит действий
- Безопасное хранение паролей

## CI/CD

Проект использует GitHub Actions для автоматизации:
- Запуск тестов при каждом пуше и PR
- Проверка качества кода (линтеры)
- Сборка Docker-образа
- Автоматический деплой на production при пуше в main

## Мониторинг

Сервис предоставляет метрики Prometheus на порту 8001:
- Количество запросов
- Время выполнения запросов
- Количество кэш-хитов и кэш-миссов

## Структура проекта

```
phone-spam-checker/
├── app/                          # Основной код приложения
│   ├── api/                      # API-слой
│   │   ├── models.py             # Модели запросов и ответов
│   │   └── routes.py             # Маршруты API
│   ├── services/                 # Сервисный слой
│   │   └── phone_checker_service.py  # Сервис проверки номеров
│   ├── repositories/             # Репозитории
│   │   └── cache_repository.py   # Репозиторий кэша
│   ├── infrastructure/           # Инфраструктурные компоненты
│   │   ├── device/               # Работа с устройствами
│   │   │   ├── device_interface.py  # Интерфейс устройства
│   │   │   ├── android_device.py    # Реализация для Android
│   │   │   └── device_manager.py    # Менеджер устройств
│   │   └── checkers/             # Стратегии проверки номеров
│   │       └── phone_checker_strategy.py  # Стратегии чекеров
│   ├── utils/                    # Утилиты
│   │   ├── constants.py          # Константы
│   │   ├── exceptions.py         # Исключения
│   │   ├── phone_utils.py        # Утилиты для работы с номерами
│   │   ├── protocols.py          # Протоколы для типизации
│   │   ├── security.py           # Безопасность и аудит
│   │   └── validators.py         # Валидаторы
│   └── main.py                   # Точка входа приложения
├── tests/                        # Тесты
│   ├── unit/                     # Модульные тесты
│   ├── integration/              # Интеграционные тесты
│   └── performance/              # Тесты производительности
├── .github/                      # GitHub Actions
│   └── workflows/                # Рабочие процессы CI/CD
│       └── ci-cd.yml             # Конфигурация CI/CD
├── Dockerfile                    # Dockerfile
├── docker-compose.yml            # Docker Compose для разработки
├── docker-compose.prod.yml       # Docker Compose для production
├── requirements.txt              # Зависимости Python
└── README.md                     # Документация
```

## Лицензия

MIT

## Автор

pichanez
