#!/bin/bash

# Скрипт копирования корпоративных документов в monitored_folder

SOURCE_DIR="$HOME/Alpaca/data/volume_documents/ЮРИСТ (МАША)/Корпоративные документы (Уставные, Учредительные, прочее)"

# Получаем путь из settings.py
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
DEST_DIR=$(cd "$PROJECT_DIR" && source venv/bin/activate && python -c "from settings import settings; print(settings.MONITORED_PATH)")

# Проверка существования исходной директории
if [ ! -d "$SOURCE_DIR" ]; then
    echo "ОШИБКА: Исходная директория не найдена:"
    echo "$SOURCE_DIR"
    exit 1
fi

# Проверка существования целевой директории
if [ ! -d "$DEST_DIR" ]; then
    echo "ОШИБКА: Целевая директория не найдена:"
    echo "$DEST_DIR"
    exit 1
fi

# Копирование файлов
echo "Копирование файлов из:"
echo "$SOURCE_DIR"
echo "в:"
echo "$DEST_DIR"
echo ""

# Подсчет файлов перед копированием
FILE_COUNT=$(find "$SOURCE_DIR" -type f | wc -l)
DIR_COUNT=$(find "$SOURCE_DIR" -type d | wc -l)

cp -rv "$SOURCE_DIR/"* "$DEST_DIR/"

if [ $? -eq 0 ]; then
    echo ""
    echo "✓ Копирование завершено успешно"
    echo "Скопировано файлов: $FILE_COUNT"
    echo "Скопировано директорий: $((DIR_COUNT - 1))"
else
    echo ""
    echo "✗ Ошибка при копировании"
    exit 1
fi
