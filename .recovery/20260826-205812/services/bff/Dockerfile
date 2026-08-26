FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN useradd -m -u 1001 appuser && chown -R appuser:appuser /app
USER appuser

HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=20s \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8095/health')" || exit 1

EXPOSE 8095
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8095", "--workers", "4"]
