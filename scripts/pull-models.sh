#!/usr/bin/env bash
# Download the local models once on a connected machine. They are stored in the
# ollama volume that the offline stack reads from.
set -euo pipefail

CHAT_MODEL="${OFFLINE_CHAT_MODEL:-llama3.1:8b}"
EMBED_MODEL="${OFFLINE_EMBED_MODEL:-nomic-embed-text}"

docker compose -f compose.setup.yaml up -d
trap 'docker compose -f compose.setup.yaml down' EXIT
sleep 3
docker compose -f compose.setup.yaml exec ollama-setup ollama pull "$CHAT_MODEL"
docker compose -f compose.setup.yaml exec ollama-setup ollama pull "$EMBED_MODEL"
docker compose -f compose.setup.yaml exec ollama-setup ollama list
