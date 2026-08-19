# HSAAI API Gateway — Production-Ready Docker Image (v2.2)
FROM python:3.12-slim AS builder
WORKDIR /app
# FIX B-15: Copy the service requirements AND the shared
# packages/common/requirements.txt (referenced via `-r` from the service
# file) so pip can resolve the consolidated shared dependencies.
COPY services/api_gateway/requirements.txt ./services/api_gateway/requirements.txt
COPY packages/common/requirements.txt ./packages/common/requirements.txt
RUN pip install --no-cache-dir --user -r ./services/api_gateway/requirements.txt

FROM python:3.12-slim
RUN adduser --disabled-password --gecos "" --uid 1000 appuser
WORKDIR /app
# FIX v2.2 (Phase 2): Build from project root so launcher + packages/common are available.
COPY --from=builder /root/.local /home/appuser/.local
COPY services/api_gateway /app/api_gateway
COPY packages/common /app/packages/common
ENV PYTHONPATH=/app
RUN chown -R appuser:appuser /app
USER appuser
ENV PATH=/home/appuser/.local/bin:$PATH
WORKDIR /app/api_gateway
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8060/health')" || exit 1
EXPOSE 8060
# FIX v2.2 (Phase 2): Use launcher with mTLS support (reads MTLS_* env vars automatically).
CMD ["python", "-m", "packages.common.launcher", "--app", "main:app", "--host", "0.0.0.0", "--port", "8060", "--workers", "4"]
