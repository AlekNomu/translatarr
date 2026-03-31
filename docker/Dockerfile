FROM node:20-alpine AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.13-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        ffmpeg \
        gosu \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

ENV UV_SYSTEM_PYTHON=1

COPY pyproject.toml README.md LICENSE ./
COPY backend/ backend/

# Install CPU-only torch first to avoid pulling the large CUDA build from PyPI
RUN uv pip install torch --index-url https://download.pytorch.org/whl/cpu \
    && uv pip install .

COPY --from=frontend-build /app/backend/translatarr_web/static/ backend/translatarr_web/static/

COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 6868
VOLUME ["/config"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:6868/api/system/status || exit 1

ENTRYPOINT ["/entrypoint.sh"]
CMD ["translatarr", "--config-dir", "/config", "--host", "0.0.0.0", "--port", "6868"]
