# HSAAI LLM Gateway — Production-Ready Docker Image
#
# FIX CRITICAL-3 (HSAAI-DEP-2026-07-11): Build context is the project root
# (set automatically by docker-compose). Copy the service folder plus
# packages/common so the relative import `from .model_router import ...`
# in main.py resolves correctly when uvicorn is launched as
# `uvicorn llm_gateway.main:app` with PYTHONPATH=/app.
FROM python:3.12-slim AS builder
WORKDIR /app
COPY services/llm_gateway/requirements.txt ./services/llm_gateway/requirements.txt
COPY packages/common/requirements.txt ./packages/common/requirements.txt
RUN pip install --no-cache-dir --user -r ./services/llm_gateway/requirements.txt

FROM python:3.12-slim
RUN adduser --disabled-password --gecos "" --uid 1000 appuser
WORKDIR /app
COPY --from=builder /root/.local /home/appuser/.local
COPY services/llm_gateway /app/llm_gateway
COPY packages/common /app/packages/common
# Ensure llm_gateway is importable as a package
RUN touch /app/llm_gateway/__init__.py
RUN chown -R appuser:appuser /app
USER appuser
ENV PYTHONPATH=/app
ENV PATH=/home/appuser/.local/bin:$PATH
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8090/health')" || exit 1
EXPOSE 8090
CMD ["uvicorn", "llm_gateway.main:app", "--host", "0.0.0.0", "--port", "8090", "--workers", "2"]
