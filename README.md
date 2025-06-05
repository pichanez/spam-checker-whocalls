# Phone Spam Checker

This project provides a FastAPI service and CLI utilities for checking phone numbers using
Kaspersky Who Calls, Truecaller and GetContact running on connected Android devices.

## Requirements

- Python 3.10 (see `.python-version` for the exact patch version)
- ADB installed and accessible if running locally
- Connected Android devices for each service
- Pinned package versions listed in `requirements.txt`

## Environment Variables

The application loads its configuration from environment variables. The most important ones are:

- `API_KEY` – token required to access the API.
- `SECRET_KEY` – secret key used to sign JWT tokens.
- `KASP_ADB_HOST` / `KASP_ADB_PORT` – address of the device with Kaspersky Who Calls.
- `TC_ADB_HOST` / `TC_ADB_PORT` – address of the device with Truecaller.
- `GC_ADB_HOST` / `GC_ADB_PORT` – address of the device with GetContact.
- `KASP_DEVICES` – comma-separated list of Kaspersky device addresses.
- `TC_DEVICES` – comma-separated list of Truecaller device addresses.
- `GC_DEVICES` – comma-separated list of GetContact device addresses.
- `JOB_DB_PATH` – path to the SQLite file storing job statuses.
- `PG_HOST` / `PG_PORT` – address of the Postgres server.
- `PG_DB` – database name.
- `PG_USER` / `PG_PASSWORD` – credentials for Postgres.
- `LOG_LEVEL` – logging verbosity (e.g. `INFO`, `DEBUG`).
- `LOG_FORMAT` – Python logging format string.
- `LOG_FILE` – optional path to a file where logs will be written.
- `WORKER_COUNT` – how many background workers process jobs.
- `TOKEN_TTL_HOURS` – lifetime of issued JWT tokens in hours.
- `CHECKER_MODULES` – comma-separated list of modules with extra checkers.
- `USE_REDIS` – set to `1` to enable distributed mode using Redis.
- `REDIS_HOST` / `REDIS_PORT` – address of the Redis server.

`*_DEVICES` variables override the single `*_ADB_HOST`/`*_ADB_PORT` settings and
allow specifying multiple devices separated by commas. If not set, the host/port
values are used.

Values can be provided in an `.env` file which is read by `docker-compose`.

When `USE_REDIS` is enabled the service stores device pools and job queues in
Redis allowing multiple instances to work together.
The provided `docker-compose` files run a Redis container and enable this mode by default.

## Running with Docker

A simple way to start the service is via `docker-compose` which will launch the API along with Postgres and Redis:

```bash
# create .env file with all required variables
cp .env.example .env  # then edit values

# build and run the API
docker-compose up --build
```

The API will be available on <http://localhost:8000>.

### API usage

First obtain a JWT token using the login endpoint:

```bash
curl -X POST http://localhost:8000/login -H "X-API-Key: <your api key>"
```

Use the returned `access_token` with the `Authorization` header in further requests.

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/login -H "X-API-Key: <your api key>" | jq -r .access_token)
curl -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"numbers": ["123"], "service": "auto"}' \
     http://localhost:8000/check_numbers
```

POST `/check_numbers` expects JSON body:

```json
{
  "numbers": ["123"],
  "service": "auto"  // or "kaspersky", "truecaller", "getcontact"
}
```

The `service` field controls which checker is used. By default (`"auto"`) the
service will choose Kaspersky for Russian numbers and Truecaller otherwise.
If a required ADB device is unreachable the API responds with HTTP 503 and a
message describing the problem.

## Running locally

Install dependencies and launch `uvicorn`:

```bash
pip install -r requirements.txt
export API_KEY=your-key
export SECRET_KEY=your-secret
uvicorn phone_spam_checker.api:app --host 0.0.0.0 --port 8000
```

`phone_spam_checker.api` автоматически настраивает логирование и
регистрирует встроенные чекеры при старте приложения. Если вы
используете библиотеку в собственной точке входа, вызовите
`phone_spam_checker.bootstrap.initialize()` перед запуском сервиса.

Before starting, ensure ADB can reach the devices:

```bash
adb connect ${KASP_ADB_HOST}:${KASP_ADB_PORT}
adb connect ${TC_ADB_HOST}:${TC_ADB_PORT}
adb connect ${GC_ADB_HOST}:${GC_ADB_PORT}
```
### CLI usage

Run checks without the API using:

```bash
python -m scripts.phone_checker_cli SERVICE --input phones.txt --output results.csv --device 127.0.0.1:5555
```

Replace `SERVICE` with `kaspersky`, `truecaller` or `getcontact`. Any additional arguments are passed to the chosen checker.

В сценариях командной строки инициализация выполняется автоматически,
поэтому достаточно запустить скрипт, как показано выше.


## Tests

Run the unit tests (requires the optional dependency `httpx` for API tests) with:

```bash
pytest -q
```
