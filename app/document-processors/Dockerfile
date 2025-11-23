# Используем официальный образ Unstructured с предустановленными OCR зависимостями
# Включает: Tesseract OCR, Poppler, ImageMagick, языковые пакеты
FROM downloads.unstructured.io/unstructured-io/unstructured:latest

# Устанавливаем ImageMagick, Ghostscript как root (до смены пользователя)
USER root
RUN apk add --no-cache imagemagick ghostscript tzdata

# Создаём рабочую директорию
WORKDIR /app

# Копируем requirements и устанавливаем зависимости
COPY document-processors/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем исходный код
COPY document-processors/src/ ./src/
COPY shared/ ./shared/

# Создаём директории для логов и данных
RUN mkdir -p /volume_watcher /volume_md

# Переменные окружения
ENV PYTHONPATH=/app:/app/src:/app/shared/logging:/app/shared/config:/app/shared/messaging:/app/shared/celery
ENV PYTHONUNBUFFERED=1
ENV TZ=Europe/Moscow
ENV SERVICE_NAME=celery-workers

# Запускаем Celery worker (можно переопределить через docker-compose)
CMD ["celery", "-A", "tasks", "worker", "--loglevel=info", "--concurrency=4"]
