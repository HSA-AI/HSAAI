# HSAAI AI Alignment Service — Production-Ready Docker Image
# Includes: Constitutional AI + Safety Layer (merged from ai_safety)
# ============================================================
FROM python:3.12-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ && \
    rm -rf /var/lib/apt/lists/*

# Copy requirements first for layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# ─── Runtime Stage ─────────────────────────────────────────────────
FROM python:3.12-slim

# Create non-root user for security
RUN adduser --disabled-password --gecos "" --uid 1000 appuser

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /root/.local /home/appuser/.local

# Copy service code
COPY main.py alignment_layer.py safety_layer.py ./

# Copy shared packages
COPY --from=builder /app /app

# Set ownership
RUN chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Environment configuration
ENV PYTHONPATH=/app
ENV PATH=/home/appuser/.local/bin:$PATH
ENV DEPLOY_ENV=production
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Health check — verifies the service is responding
HEALTHCHECK --interval=30s --timeout=5s --retries=3 --start-period=10s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8005/health')" || exit 1

EXPOSE 8005

# Graceful shutdown: uvicorn handles SIGTERM/SIGINT
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8005", "--workers", "2", "--timeout-keep-alive", "30"]
