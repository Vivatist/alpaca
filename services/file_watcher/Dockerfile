FROM python:3.13-slim

WORKDIR /app

# Устанавливаем системные зависимости
RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Устанавливаем Python-зависимости
COPY services/file_watcher/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Копируем код сервиса
COPY services/file_watcher /app
RUN chmod +x /app/entrypoint.sh

# Копируем монолит (доменные и инфраструктурные пакеты)
COPY core /opt/alpaca/core
COPY utils /opt/alpaca/utils
ENV PYTHONPATH="/opt/alpaca:${PYTHONPATH}"

# Создаем точку монтирования для наблюдаемой папки
RUN mkdir -p /monitored_folder

# Запускаем через entrypoint (API + Scanner)
CMD ["/app/entrypoint.sh"]
