#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
command -v docker >/dev/null || { echo "Install Docker with Compose v2 first: https://docs.docker.com/engine/install/" >&2; exit 1; }
docker compose version
docker compose up -d --build --wait --wait-timeout 180
web_address="$(docker compose port web 80)"
echo "Reconfigurable SAGIN Copilot is ready: http://${web_address}"
