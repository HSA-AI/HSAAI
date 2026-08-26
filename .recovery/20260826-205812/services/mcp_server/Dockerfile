# HSAAI MCP Server (v3.1)
# FIX v2.1 (P0): Build context is now the project root to avoid illegal `../../` escape.
FROM python:3.12-slim AS builder
WORKDIR /app
COPY services/mcp_server/requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

FROM python:3.12-slim
RUN adduser --disabled-password --gecos "" --uid 1000 appuser
WORKDIR /app
COPY --from=builder /root/.local /home/appuser/.local
COPY services/mcp_server /app/mcp_server
COPY packages/common /app/packages/common
RUN chown -R appuser:appuser /app
USER appuser
ENV PATH=/home/appuser/.local/bin:$PATH
ENV PYTHONPATH=/app
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8094/health')" || exit 1
EXPOSE 8094
CMD ["uvicorn", "mcp_server.main:app", "--host", "0.0.0.0", "--port", "8094", "--workers", "2"]
