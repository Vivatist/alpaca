#!/bin/bash

# Скрипт копирования тестовых документов в monitored_folder

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Читаем пути из .env или используем дефолтные
if [ -f "$PROJECT_DIR/services/.env" ]; then
    source "$PROJECT_DIR/services/.env" 2>/dev/null || true
fi

# Путь назначения (относительно проекта)
DEST_DIR="${MONITORED_FOLDER_PATH:-$PROJECT_DIR/monitored_folder}"

# Источник можно передать как аргумент или использовать дефолтный
SOURCE_DIR="${1:-}"

if [ -z "$SOURCE_DIR" ]; then
    echo "Использование: $0 <путь_к_документам>"
    echo ""
    echo "Пример:"
    echo "  $0 ~/Documents/test_files"
    echo "  $0 /path/to/corporate/documents"
    echo ""
    echo "Целевая папка: $DEST_DIR"
    exit 1
fi

# Проверка существования исходной директории
if [ ! -d "$SOURCE_DIR" ]; then
    echo "✗ Исходная директория не найдена: $SOURCE_DIR"
    exit 1
fi

# Создание целевой директории если не существует
if [ ! -d "$DEST_DIR" ]; then
    mkdir -p "$DEST_DIR"
    echo "✓ Создана директория: $DEST_DIR"
fi

# Подсчет файлов
FILE_COUNT=$(find "$SOURCE_DIR" -type f | wc -l)

echo "=== КОПИРОВАНИЕ ДОКУМЕНТОВ ==="
echo ""
echo "Из: $SOURCE_DIR"
echo "В:  $DEST_DIR"
echo "Файлов: $FILE_COUNT"
echo ""

read -p "Продолжить? (y/n): " confirm
if [ "$confirm" != "y" ]; then
    echo "Отменено."
    exit 0
fi

cp -rv "$SOURCE_DIR/"* "$DEST_DIR/"

echo ""
echo "✓ Копирование завершено"
