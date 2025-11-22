#!/bin/bash

# Скрипт очистки monitored_folder

# Получаем путь из settings.py
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
MONITORED_DIR=$(cd "$PROJECT_DIR" && source venv/bin/activate && python -c "from settings import settings; print(settings.MONITORED_PATH)")

# Проверка существования директории
if [ ! -d "$MONITORED_DIR" ]; then
    echo "⚠️  Директория не найдена:"
    echo "$MONITORED_DIR"
    echo ""
    read -p "Создать директорию? (yes/no): " create_dir
    
    if [ "$create_dir" = "yes" ]; then
        mkdir -p "$MONITORED_DIR"
        if [ $? -eq 0 ]; then
            echo "✓ Директория создана: $MONITORED_DIR"
            echo ""
            echo "Директория пуста, нечего удалять."
            exit 0
        else
            echo "✗ Ошибка при создании директории"
            exit 1
        fi
    else
        echo "Отменено."
        exit 0
    fi
fi

# Подсчет файлов и директорий перед удалением
FILE_COUNT=$(find "$MONITORED_DIR" -type f | wc -l)
DIR_COUNT=$(find "$MONITORED_DIR" -mindepth 1 -type d | wc -l)

echo "=== ОЧИСТКА MONITORED FOLDER ==="
echo ""
echo "Директория: $MONITORED_DIR"
echo "Найдено файлов: $FILE_COUNT"
echo "Найдено поддиректорий: $DIR_COUNT"
echo ""

# Запрос подтверждения
read -p "Удалить все содержимое? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo "Отменено."
    exit 0
fi

# Удаление содержимого (оставляем саму папку)
echo ""
echo "Удаление содержимого..."
rm -rf "$MONITORED_DIR"/*

if [ $? -eq 0 ]; then
    echo ""
    echo "✓ Очистка завершена успешно"
    echo "Удалено файлов: $FILE_COUNT"
    echo "Удалено директорий: $DIR_COUNT"
    echo ""
    echo "Текущее содержимое:"
    ls -la "$MONITORED_DIR" | tail -5
else
    echo ""
    echo "✗ Ошибка при удалении"
    exit 1
fi
