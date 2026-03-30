FROM node:20-alpine AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        ffmpeg \
        gosu \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml README.md LICENSE ./
COPY translatarr/ translatarr/
COPY translatarr_web/ translatarr_web/
RUN pip install --no-cache-dir .

COPY --from=frontend-build /app/translatarr_web/static/ translatarr_web/static/

COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 6868
VOLUME ["/config", "/movies", "/tv"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:6868/api/system/status || exit 1

ENTRYPOINT ["/entrypoint.sh"]
CMD ["translatarr", "--config-dir", "/config", "--host", "0.0.0.0", "--port", "6868"]
