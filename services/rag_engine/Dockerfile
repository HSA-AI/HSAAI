# HSAAI RAG Engine — Production-Ready Docker Image (v2.1)
# FIX v2.1 (P0): Build context is now the project root so we can COPY packages/common
#   without using the illegal `../` escape. Use:
#     docker build -f services/rag_engine/Dockerfile -t hsaai/rag_engine:v2.1 .
#   from the project root, or rely on docker-compose which sets context: .. automatically.
FROM python:3.12-slim AS builder
WORKDIR /app
COPY services/rag_engine/requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

FROM python:3.12-slim
RUN adduser --disabled-password --gecos "" --uid 1000 appuser
WORKDIR /app
# FIX v2.0: Copy as package + set PYTHONPATH for relative imports
COPY --from=builder /root/.local /home/appuser/.local
# FIX v2.1: copy service source from project-root build context
COPY services/rag_engine /app/rag_engine
# FIX v2.1: copy shared packages/common from project-root build context (legal path)
COPY packages/common /app/packages/common
RUN mkdir -p /data/local_uploads /data/rag_events.db && chown -R appuser:appuser /app /data
USER appuser
ENV PATH=/home/appuser/.local/bin:$PATH
ENV PYTHONPATH=/app
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8030/health')" || exit 1
EXPOSE 8030
CMD ["uvicorn", "rag_engine.main:app", "--host", "0.0.0.0", "--port", "8030", "--workers", "2"]
