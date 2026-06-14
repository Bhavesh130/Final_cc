#!/usr/bin/env bash
# Stop and remove the FinAlly container (data volume is preserved).
set -euo pipefail

CONTAINER="finally"

if [[ -n "$(docker ps -aq -f name="^${CONTAINER}$")" ]]; then
  docker rm -f "$CONTAINER" >/dev/null
  echo "Stopped and removed container '${CONTAINER}'. Data volume 'finally-data' kept."
else
  echo "No container named '${CONTAINER}' is running."
fi
