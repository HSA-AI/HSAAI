@echo off
set OLLAMA_HOST=http://localhost:11434
for %%M in (qwen3:8b llama3.1:8b-instruct mistral:7b-instruct) do (
  echo Pulling %%M ...
  curl -fsS %OLLAMA_HOST%/api/pull -d "{\"name\":\"%%M\"}"
  echo Done %%M
)
