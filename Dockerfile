# Use slim Python 3.11 image
FROM python:3.11-slim

# Install ADB for Android interaction
RUN apt-get update \
    && apt-get install -y --no-install-recommends android-tools-adb \
    && rm -rf /var/lib/apt/lists/*

# Working directory
WORKDIR /app

# Copy project code
COPY . .

# Install Python dependencies
RUN pip install --no-cache-dir hatchling && pip install --no-cache-dir .

# Create entrypoint script inside container without CRLF
RUN printf '#!/bin/sh\n' > /entrypoint.sh \
    && printf 'adb connect ${KASP_ADB_HOST}:${KASP_ADB_PORT}\n' >> /entrypoint.sh \
    && printf 'adb connect ${TC_ADB_HOST}:${TC_ADB_PORT}\n' >> /entrypoint.sh \
    && printf 'adb connect ${GC_ADB_HOST}:${GC_ADB_PORT}\n' >> /entrypoint.sh \
    && printf 'exec uvicorn phone_spam_checker.api:app --host 0.0.0.0 --port 8000\n' >> /entrypoint.sh \
    && chmod +x /entrypoint.sh

# Expose FastAPI port
EXPOSE 8000

# Use entrypoint to start the application
ENTRYPOINT ["/entrypoint.sh"]