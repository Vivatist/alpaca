FROM python:3.13-slim

WORKDIR /app

# Устанавливаем системные зависимости
RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Копируем requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем код сервиса
COPY . /app/

# Создаем точку монтирования для наблюдаемой папки
RUN mkdir -p /monitored_folder

# Запускаем file_watcher
CMD ["python", "/app/main.py"]
