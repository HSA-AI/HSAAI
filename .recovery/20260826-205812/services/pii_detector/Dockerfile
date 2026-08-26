# HSAAI PII Detector — Docker Image (v3.0)
FROM python:3.12-slim AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt
# Download spacy model
RUN python -m spacy download en_core_web_sm

FROM python:3.12-slim
RUN adduser --disabled-password --gecos "" appuser
WORKDIR /app
COPY --from=builder /root/.local /home/appuser/.local
COPY --from=builder /usr/local/lib/python3.12/site-packages/en_core_web_sm /usr/local/lib/python3.12/site-packages/en_core_web_sm
COPY . /app/pii_detector
RUN chown -R appuser:appuser /app
USER appuser
ENV PATH=/home/appuser/.local/bin:$PATH
ENV PYTHONPATH=/app
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8092/health')" || exit 1
EXPOSE 8092
CMD ["uvicorn", "pii_detector.main:app", "--host", "0.0.0.0", "--port", "8092", "--workers", "2"]
