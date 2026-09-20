# HSAAI: root-context multi-stage image, shared authentication included.
FROM python:3.12-slim AS builder
WORKDIR /build
COPY services/quantum_decision_engine/requirements.txt services/quantum_decision_engine/requirements.txt
COPY packages/common/requirements.txt packages/common/requirements.txt
RUN pip install --no-cache-dir --prefix=/install -r services/quantum_decision_engine/requirements.txt

FROM python:3.12-slim AS runtime
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/*
RUN adduser --disabled-password --gecos "" --uid 1000 appuser
WORKDIR /app
COPY --from=builder /install /usr/local
COPY services/quantum_decision_engine /app/services/quantum_decision_engine
COPY packages /app/packages
RUN mkdir -p /data/local_uploads /app/storage /app/tmp && chown -R appuser:appuser /app /data
ENV PYTHONPATH=/app:/app/services:/app/services/quantum_decision_engine:/app/packages \
    PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
USER appuser
HEALTHCHECK --interval=30s --timeout=5s --retries=3 --start-period=30s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8086/health', timeout=4)" || exit 1
EXPOSE 8086
CMD ["uvicorn", "quantum_decision_engine.main:app", "--host", "0.0.0.0", "--port", "8086", "--workers", "1"]
