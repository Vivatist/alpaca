# Chat Backend Service
FROM python:3.11-slim

WORKDIR /app

# Системные зависимости (curl для healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Python зависимости
COPY services/chat_backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Исходники
COPY services/chat_backend/src/ ./src/

# Переменные окружения
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/src

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
