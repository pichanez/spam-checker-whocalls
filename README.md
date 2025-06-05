# Phone Spam Checker

This project provides CLI tools and a FastAPI service for checking phone numbers through Android applications (Kaspersky Who Calls, Truecaller and GetContact).

## Installation

1. Ensure you have **Python 3.10** and **ADB** installed.
2. Clone this repository and install dependencies:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

## Environment variables

The API requires a key and addresses of Android devices running the checker applications.

- `API_KEY` – token required for API requests.
- `KASP_ADB_HOST` / `KASP_ADB_PORT` – host and port of the device with Kaspersky Who Calls.
- `TC_ADB_HOST` / `TC_ADB_PORT` – host and port of the device with Truecaller.
- `GC_ADB_HOST` / `GC_ADB_PORT` – host and port of the device with GetContact.

Example `.env` file used by Docker Compose:
```env
API_KEY=your-super-secret-key
KASP_ADB_HOST=127.0.0.1
KASP_ADB_PORT=5555
TC_ADB_HOST=127.0.0.1
TC_ADB_PORT=5556
GC_ADB_HOST=127.0.0.1
GC_ADB_PORT=5557
```

## Running the API

After exporting all environment variables, start the service with Uvicorn:
```bash
uvicorn api:app --host 0.0.0.0 --port 8000
```

## CLI tools

Each checker can be run directly for ad-hoc checks. Examples:
```bash
python kaspersky_phone_checker.py -i phones.txt -o kasp.csv -d 127.0.0.1:5555
python truecaller_phone_checker.py -i phones.txt -o truecaller.csv -d 127.0.0.1:5556
python getcontact_phone_checker.py -i phones.txt -o getcontact.csv -d 127.0.0.1:5557
```

## Docker usage

Build the image and run it directly:
```bash
docker build -t phone-checker .
docker run -p 8000:8000 --env-file .env phone-checker
```

Or use Docker Compose for development:
```bash
docker compose up --build
```
For production, use `docker-compose.prod.yml`:
```bash
docker compose -f docker-compose.prod.yml up --build -d
```
