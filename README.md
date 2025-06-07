# Phone Spam Checker

This project provides a FastAPI service and CLI utilities for checking phone numbers using
Kaspersky Who Calls, Truecaller, GetContact running on connected Android devices,
and the Tbank web service for Russian numbers.

## Requirements

- Python 3.11 (см. `.python-version` для точной версии)
- ADB установлен и доступен при локальном запуске
- Подключённые Android‑устройства для каждого сервиса
- Зависимости описаны в `pyproject.toml`

## Environment Variables

The application loads its configuration from environment variables. The most important ones are:

- `API_KEY` – token required to access the API.
- `SECRET_KEY` – secret key used to sign JWT tokens.
- `SECRET_KEYS` – optional comma-separated list of additional keys accepted when verifying JWTs.
- `TOKEN_AUDIENCE` – expected audience claim for JWT tokens.
- `TOKEN_ISSUER` – issuer claim for JWT tokens.
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
- `LOG_JSON` – set to `1` for JSON log formatting.
- `LOG_MAX_BYTES` – rotate `LOG_FILE` after this size (bytes).
- `LOG_BACKUP_COUNT` – how many rotated log files to keep.
- `LOG_REMOTE_HOST` / `LOG_REMOTE_PORT` – optional remote log collector.
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
  "service": "auto"  // or "kaspersky", "truecaller", "getcontact", "tbank"
}
```

The `service` field controls which checker is used. By default (`"auto"`)
Russian numbers are verified via Kaspersky Who Calls, GetContact and the
Tbank web service, while Truecaller is used only for international numbers.
If a required ADB device is unreachable the API responds with HTTP 503 and a
message describing the problem.

To query results or progress of a task, call the `/status/{job_id}` endpoint
with the same authorization header. The response contains the job status and any
results collected so far.

## Running locally

Install dependencies and launch `uvicorn`:

```bash
pip install hatch
pip install -e .[develop]
export API_KEY=your-key
export SECRET_KEY=your-secret
uvicorn phone_spam_checker.api:app --host 0.0.0.0 --port 8000
```

`phone_spam_checker.api` automatically configures logging and registers the
built-in checkers when imported. If you start the service from your own entry
point, call `phone_spam_checker.bootstrap.initialize()` first.

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

Replace `SERVICE` with `kaspersky`, `truecaller`, `getcontact` or `tbank`. Any
additional arguments are forwarded to the selected checker. Initialization is
performed automatically in the CLI tools, so simply run the command above.


## Tests

Run the unit tests (requires the optional dependency `httpx` for API tests) with:

```bash
pytest -q
```
