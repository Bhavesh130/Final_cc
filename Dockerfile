# syntax=docker/dockerfile:1

# ---------- Stage 1: build the Next.js static export ----------
FROM node:20-slim AS frontend
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci
COPY frontend/ ./
RUN npm run build   # produces /frontend/out (output: 'export')

# ---------- Stage 2: Python backend runtime ----------
FROM python:3.12-slim AS backend

# uv for fast, reproducible dependency installs.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app
ENV FINALLY_DB_PATH=/app/db/finally.db \
    FINALLY_STATIC_DIR=/app/static \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

# Install dependencies first (cached layer) using only the lock + metadata.
COPY backend/pyproject.toml backend/uv.lock backend/README.md ./
RUN uv sync --frozen --no-dev --no-install-project

# Copy backend source and install the project itself.
COPY backend/ ./
RUN uv sync --frozen --no-dev

# Bring in the built frontend.
COPY --from=frontend /frontend/out ./static

# Runtime DB volume mount point.
RUN mkdir -p /app/db

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
