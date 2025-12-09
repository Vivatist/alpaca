#!/bin/bash

# Скрипт очистки monitored_folder и tmp_md

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Читаем пути из .env или используем дефолтные
if [ -f "$PROJECT_DIR/services/.env" ]; then
    source "$PROJECT_DIR/services/.env" 2>/dev/null || true
fi

# Пути по умолчанию (относительно проекта)
MONITORED_DIR="${MONITORED_FOLDER_PATH:-$PROJECT_DIR/monitored_folder}"
TMP_MD_DIR="${TMP_MD_PATH:-$PROJECT_DIR/tmp_md}"

echo "=== ОЧИСТКА MONITORED FOLDER ==="
echo ""
echo "Monitored: $MONITORED_DIR"
echo "Tmp MD:    $TMP_MD_DIR"
echo ""

# Проверка существования директории
if [ ! -d "$MONITORED_DIR" ]; then
    echo "⚠️  Директория не найдена: $MONITORED_DIR"
    read -p "Создать директорию? (y/n): " create_dir
    
    if [ "$create_dir" = "y" ]; then
        mkdir -p "$MONITORED_DIR"
        echo "✓ Директория создана"
        exit 0
    else
        echo "Отменено."
        exit 0
    fi
fi

# Подсчет файлов
FILE_COUNT=$(find "$MONITORED_DIR" -type f 2>/dev/null | wc -l)
DIR_COUNT=$(find "$MONITORED_DIR" -mindepth 1 -type d 2>/dev/null | wc -l)

echo "Найдено файлов: $FILE_COUNT"
echo "Найдено поддиректорий: $DIR_COUNT"
echo ""

read -p "Удалить все содержимое? (y/n): " confirm

if [ "$confirm" != "y" ]; then
    echo "Отменено."
    exit 0
fi

# Очистка monitored_folder
echo "Очистка monitored_folder..."
rm -rf "$MONITORED_DIR"/* 2>/dev/null || true
echo "✓ monitored_folder очищена"

# Очистка tmp_md
if [ -d "$TMP_MD_DIR" ]; then
    echo "Очистка tmp_md..."
    rm -rf "$TMP_MD_DIR"/* 2>/dev/null || true
    echo "✓ tmp_md очищена"
fi

echo ""
echo "✓ Очистка завершена"
