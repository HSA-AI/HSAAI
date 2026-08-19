# Local LLM Operations

## Supported local backends

- Ollama: recommended simple enterprise baseline.
- llama.cpp server: lightweight offline serving.
- vLLM: recommended GPU production serving.

## Recommended models

| Model | Use |
|---|---|
| Qwen2.5 | Arabic/English enterprise assistant, strong multilingual ability |
| Llama 3.1/3.2 | General enterprise chat and reasoning |
| Mistral | Efficient internal assistant tasks |

## Ollama quick start

```bash
ollama pull qwen2.5:7b
ollama pull llama3.1:8b
ollama pull mistral:7b
```

Set:

```bash
LOCAL_LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://ollama:11434
DEFAULT_LOCAL_MODEL=qwen2.5:7b
STRICT_INTERNAL_ONLY=true
DISABLE_EXTERNAL_AI_PROVIDERS=true
```

## Production notes

- Put model storage on persistent disk.
- Restrict model API to internal network.
- Monitor GPU memory, latency, token throughput, and model errors.
- Keep a smaller fallback model for degraded mode.
