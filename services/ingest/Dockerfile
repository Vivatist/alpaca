FROM python:3.11-slim

# Установка системных зависимостей для парсеров
RUN apt-get update && apt-get install -y --no-install-recommends \
    # LibreOffice для конвертации .doc/.xls/.ppt
    libreoffice \
    # ImageMagick для конвертации WMF/EMF изображений
    imagemagick \
    libmagickwand-dev \
    # Поддержка WMF формата
    libwmf-bin \
    # Tesseract для OCR
    tesseract-ocr \
    tesseract-ocr-rus \
    tesseract-ocr-eng \
    # poppler для pdf2image
    poppler-utils \
    # Сборка psycopg2
    libpq-dev \
    gcc \
    # Очистка кеша
    && rm -rf /var/lib/apt/lists/* \
    # Разрешить ImageMagick конвертировать WMF/EMF/PDF
    && sed -i 's/rights="none" pattern="PDF"/rights="read|write" pattern="PDF"/' /etc/ImageMagick-6/policy.xml || true \
    && sed -i 's/rights="none" pattern="PS"/rights="read|write" pattern="PS"/' /etc/ImageMagick-6/policy.xml || true \
    && sed -i 's/rights="none" pattern="EPS"/rights="read|write" pattern="EPS"/' /etc/ImageMagick-6/policy.xml || true \
    && sed -i '/<\/policymap>/i <policy domain="coder" rights="read|write" pattern="WMF" \/>' /etc/ImageMagick-6/policy.xml || true \
    && sed -i '/<\/policymap>/i <policy domain="coder" rights="read|write" pattern="EMF" \/>' /etc/ImageMagick-6/policy.xml || true

WORKDIR /app

# Копируем зависимости
COPY services/ingest/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем код сервиса
COPY services/ingest/src/ ./src/

# Создаём директории для данных
RUN mkdir -p /tmp_md /monitored_folder

# Точка входа
ENV PYTHONPATH=/app/src
CMD ["python", "-m", "main"]
