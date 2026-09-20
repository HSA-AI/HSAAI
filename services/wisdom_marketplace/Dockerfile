# HSAAI: root-context multi-stage image, shared authentication included.
FROM python:3.12-slim AS builder
WORKDIR /build
COPY services/wisdom_marketplace/requirements.txt services/wisdom_marketplace/requirements.txt
COPY packages/common/requirements.txt packages/common/requirements.txt
RUN pip install --no-cache-dir --prefix=/install -r services/wisdom_marketplace/requirements.txt

FROM python:3.12-slim AS runtime
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/*
RUN adduser --disabled-password --gecos "" --uid 1000 appuser
WORKDIR /app
COPY --from=builder /install /usr/local
COPY services/wisdom_marketplace /app/services/wisdom_marketplace
COPY packages /app/packages
RUN mkdir -p /data/local_uploads /app/storage /app/tmp && chown -R appuser:appuser /app /data
ENV PYTHONPATH=/app:/app/services:/app/services/wisdom_marketplace:/app/packages \
    PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
USER appuser
HEALTHCHECK --interval=30s --timeout=5s --retries=3 --start-period=30s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8074/health', timeout=4)" || exit 1
EXPOSE 8074
CMD ["uvicorn", "wisdom_marketplace.main:app", "--host", "0.0.0.0", "--port", "8074", "--workers", "1"]
