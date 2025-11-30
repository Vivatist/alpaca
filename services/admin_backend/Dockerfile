FROM python:3.13-slim

WORKDIR /app

# Установка системных зависимостей для psycopg2
RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Установка Python зависимостей
COPY services/admin_backend/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Копирование кода приложения
COPY services/admin_backend/src /app

# Копирование доменной библиотеки
COPY alpaca /opt/alpaca/alpaca
COPY utils /opt/alpaca/utils
ENV PYTHONPATH="/opt/alpaca:${PYTHONPATH}"

# Запуск FastAPI с uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
