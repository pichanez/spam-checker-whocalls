# Phone Spam Checker

This project provides a FastAPI service and CLI utilities for checking phone numbers using
Kaspersky Who Calls, Truecaller and GetContact running on connected Android devices.

## Requirements

- Python 3.10+
- ADB installed and accessible if running locally
- Connected Android devices for each service

## Environment Variables

The application loads its configuration from environment variables. The most important ones are:

- `API_KEY` – token required to access the API.
- `KASP_ADB_HOST` / `KASP_ADB_PORT` – address of the device with Kaspersky Who Calls.
- `TC_ADB_HOST` / `TC_ADB_PORT` – address of the device with Truecaller.
- `GC_ADB_HOST` / `GC_ADB_PORT` – address of the device with GetContact.

Values can be provided in an `.env` file which is read by `docker-compose`.

## Running with Docker

A simple way to start the service is via `docker-compose`:

```bash
# create .env file with all required variables
cp .env.example .env  # then edit values

# build and run the API
docker-compose up --build
```

The API will be available on <http://localhost:8000>.

## Running locally

Install dependencies and launch `uvicorn`:

```bash
pip install -r requirements.txt
export API_KEY=your-key
uvicorn api:app --host 0.0.0.0 --port 8000
```

Before starting, ensure ADB can reach the devices:

```bash
adb connect ${KASP_ADB_HOST}:${KASP_ADB_PORT}
adb connect ${TC_ADB_HOST}:${TC_ADB_PORT}
adb connect ${GC_ADB_HOST}:${GC_ADB_PORT}
```

## Tests

Run the unit tests with:

```bash
pytest -q
```
