
# FIX v2.1 (P0): Use -runtime base (~2.5GB) instead of -devel (~6GB).
# The -devel flavour is only needed when building CUDA kernels from source;
# -runtime is sufficient for inference/training with pre-built PyTorch wheels.
FROM nvidia/cuda:12.4.1-cudnn-runtime-ubuntu22.04
ENV DEBIAN_FRONTEND=noninteractive PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.11 python3.11-venv python3-pip git curl build-essential \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY services/model_training/requirements.txt /app/requirements.txt
RUN python3.11 -m pip install --upgrade pip && python3.11 -m pip install -r /app/requirements.txt
COPY services/model_training /app/services/model_training
COPY packages/common /app/packages/common
ENV PYTHONPATH=/app
EXPOSE 8090
RUN adduser --disabled-password --gecos "" --uid 1000 appuser && chown -R appuser:appuser /app
USER appuser
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python3.11 -c "import urllib.request; urllib.request.urlopen('http://localhost:8090/health')" || exit 1
CMD ["python3.11", "-m", "uvicorn", "services.model_training.main:app", "--host", "0.0.0.0", "--port", "8090"]
