FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONPATH=/app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . /app/auth_service
RUN adduser --disabled-password --gecos "" --uid 1000 appuser
USER appuser
CMD ["uvicorn", "auth_service.main:app", "--host", "0.0.0.0", "--port", "8010"]
