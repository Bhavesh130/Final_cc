#!/usr/bin/env bash
# Build (if needed) and run the FinAlly container on macOS/Linux.
# Usage: ./scripts/start_mac.sh [--build]
set -euo pipefail

IMAGE="finally:latest"
CONTAINER="finally"
VOLUME="finally-data"
PORT="8000"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ ! -f .env ]]; then
  echo "No .env found — creating one from .env.example."
  cp .env.example .env
  echo "  → Edit .env and add your OPENROUTER_API_KEY, then re-run this script."
fi

BUILD=false
[[ "${1:-}" == "--build" ]] && BUILD=true

if $BUILD || [[ -z "$(docker images -q "$IMAGE" 2>/dev/null)" ]]; then
  echo "Building image $IMAGE ..."
  docker build -t "$IMAGE" .
fi

# Replace any existing container.
if [[ -n "$(docker ps -aq -f name="^${CONTAINER}$")" ]]; then
  echo "Removing existing container ..."
  docker rm -f "$CONTAINER" >/dev/null
fi

echo "Starting container ..."
docker run -d \
  --name "$CONTAINER" \
  -p "${PORT}:8000" \
  -v "${VOLUME}:/app/db" \
  --env-file .env \
  "$IMAGE" >/dev/null

URL="http://localhost:${PORT}"
echo "FinAlly is running at ${URL}"

# Open the browser if possible.
if command -v open >/dev/null 2>&1; then
  open "$URL" || true
elif command -v xdg-open >/dev/null 2>&1; then
  xdg-open "$URL" || true
fi
