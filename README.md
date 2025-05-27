# Phone Checker API

API-сервис для проверки телефонных номеров на спам через Kaspersky Who Calls, Truecaller и GetContact.

## Обзор

Phone Checker API позволяет проверять телефонные номера на наличие информации о спаме через популярные приложения:
- Kaspersky Who Calls (для российских номеров)
- Truecaller (для международных номеров)
- GetContact (опционально для всех номеров)

Система использует Android-эмуляторы с установленными приложениями и автоматизирует взаимодействие с их интерфейсом через uiautomator2.

## Особенности

- Асинхронная обработка запросов
- Кэширование результатов в Redis
- Параллельная проверка множественных номеров
- Автоматический выбор подходящего сервиса для проверки
- Мониторинг состояния устройств
- Полное API с документацией OpenAPI
- Контейнеризация с Docker и Docker Compose

## Требования

- Python 3.10+
- Docker и Docker Compose
- Android-эмуляторы с установленными приложениями:
  - Kaspersky Who Calls
  - Truecaller
  - GetContact (опционально)
- Redis (для кэширования)

## Установка и запуск

### Подготовка Android-эмуляторов

1. Настройте Android-эмуляторы с помощью Android Studio или другого инструмента
2. Установите на эмуляторы необходимые приложения
3. Подключите эмуляторы через ADB:
   ```bash
   adb connect 127.0.0.1:5555  # Kaspersky
   adb connect 127.0.0.1:5556  # Truecaller
   adb connect 127.0.0.1:5557  # GetContact (опционально)
   ```

### Запуск с Docker Compose

1. Клонировать репозиторий:
   ```bash
   git clone https://github.com/pichanez/spam-checker-whocalls.git
   cd spam-checker-whocalls
   ```

2. Создать файл `.env`:
   ```
   API_KEY=your-super-secret-key
   KASP_ADB_HOST=host.docker.internal
   KASP_ADB_PORT=5555
   TC_ADB_HOST=host.docker.internal
   TC_ADB_PORT=5556
   GC_ADB_HOST=host.docker.internal
   GC_ADB_PORT=5557
   REDIS_URL=redis://redis:6379/0
   CACHE_TTL=86400
   CACHE_ENABLED=true
   LOG_LEVEL=INFO
   ```

3. Запустить с Docker Compose:
   ```bash
   docker-compose up -d
   ```

### Запуск без Docker

1. Установить зависимости:
   ```bash
   pip install -r requirements.txt
   ```

2. Запустить Redis:
   ```bash
   docker run -d -p 6379:6379 redis
   ```

3. Запустить API:
   ```bash
   export API_KEY=your-super-secret-key
   export KASP_ADB_HOST=127.0.0.1
   export KASP_ADB_PORT=5555
   export TC_ADB_HOST=127.0.0.1
   export TC_ADB_PORT=5556
   export GC_ADB_HOST=127.0.0.1
   export GC_ADB_PORT=5557
   export REDIS_URL=redis://localhost:6379/0
   uvicorn api:app --host 0.0.0.0 --port 8000
   ```

## Использование API

### Проверка номеров

```
POST /check_numbers
Content-Type: application/json
X-API-Key: your-super-secret-key

{
  "numbers": ["+79123456789", "+12025550108"],
  "use_cache": true,
  "force_source": null
}
```

Параметры:
- `numbers`: Список телефонных номеров для проверки
- `use_cache`: Использовать ли кэш (по умолчанию `true`)
- `force_source`: Принудительно использовать определенный источник: `"kaspersky"`, `"truecaller"` или `"getcontact"` (по умолчанию `null`)

Ответ:
```json
{
  "job_id": "a1b2c3d4e5f6"
}
```

### Получение статуса задачи

```
GET /status/a1b2c3d4e5f6
X-API-Key: your-super-secret-key
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
      "details": "Иван Петров",
      "source": "Kaspersky"
    },
    {
      "phone_number": "+12025550108",
      "status": "Spam",
      "details": "Reported as spam by 5 users",
      "source": "Truecaller"
    }
  ],
  "error": null,
  "progress": 100.0
}
```

Возможные значения `status`:
- `in_progress`: Задача выполняется
- `completed`: Задача завершена успешно
- `failed`: Задача завершена с ошибкой

Возможные значения `status` для результатов проверки:
- `Safe`: Безопасный номер
- `Spam`: Спам
- `Not in database`: Номер не найден в базе
- `Error`: Ошибка при проверке
- `Unknown`: Неизвестный статус

### Проверка состояния устройств

```
GET /device_status
X-API-Key: your-super-secret-key
```

Ответ:
```json
{
  "kaspersky": {
    "connected": true,
    "screen_on": true,
    "unlocked": true,
    "battery": "85%",
    "running_apps": "com.kaspersky.who_calls",
    "error": null
  },
  "truecaller": {
    "connected": true,
    "screen_on": true,
    "unlocked": true,
    "battery": "90%",
    "running_apps": "com.truecaller",
    "error": null
  },
  "getcontact": {
    "connected": true,
    "screen_on": true,
    "unlocked": true,
    "battery": "95%",
    "running_apps": "app.source.getcontact",
    "error": null
  }
}
```

### Очистка кэша

```
POST /cache/clear
X-API-Key: your-super-secret-key
```

Ответ:
```json
{
  "success": true,
  "message": "Cache cleared successfully"
}
```

### Проверка работоспособности

```
GET /health
```

Ответ:
```json
{
  "status": "ok"
}
```

## Документация API

Полная документация API доступна по адресу `/docs` или `/redoc` после запуска сервиса.

## Мониторинг

API предоставляет метрики Prometheus на порту 8001. Доступные метрики:
- `phone_checker_requests_total`: Общее количество запросов
- `phone_checker_check_duration_seconds`: Время, затраченное на проверку номеров
- `phone_checker_cache_hits_total`: Количество попаданий в кэш
- `phone_checker_cache_misses_total`: Количество промахов кэша

## Разработка и тестирование

### Запуск тестов

```bash
pytest
```

### Запуск линтера

```bash
flake8
```

### Запуск типизации

```bash
mypy .
```

## Архитектура

Проект построен на основе следующих компонентов:

1. **Базовые абстракции**:
   - `BasePhoneChecker`: Абстрактный базовый класс для всех чекеров
   - `PhoneCheckerFactory`: Фабрика для создания чекеров

2. **Чекеры**:
   - `KasperskyWhoCallsChecker`: Проверка через Kaspersky Who Calls
   - `TruecallerChecker`: Проверка через Truecaller
   - `GetContactChecker`: Проверка через GetContact

3. **API и асинхронная обработка**:
   - FastAPI для API
   - Асинхронная обработка запросов
   - Фоновые задачи

4. **Кэширование**:
   - Redis для кэширования результатов
   - Асинхронный доступ к кэшу

5. **Мониторинг**:
   - Prometheus метрики
   - Логирование

## Лицензия

MIT
