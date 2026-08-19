#!/usr/bin/env bash
set -euo pipefail
OLLAMA_HOST="${OLLAMA_HOST:-http://localhost:11434}"
MODELS=("qwen3:8b" "llama3.1:8b-instruct" "mistral:7b-instruct")

printf 'HSAAI Ollama bootstrap using %s\n' "$OLLAMA_HOST"
for model in "${MODELS[@]}"; do
  printf 'Pulling %s ...\n' "$model"
  curl -fsS "$OLLAMA_HOST/api/pull" -d "{\"name\":\"$model\"}"
  printf '\nDone: %s\n' "$model"
done
