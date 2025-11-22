#!/bin/bash
# Скрипт для запуска всех тестов file-watcher

set -e

# Проверяем что контейнер с БД запущен
if ! docker ps | grep -q supabase-db; then
    echo "ОШИБКА: Контейнер supabase-db не запущен"
    echo "Запустите: docker compose up -d"
    exit 1
fi

echo "=========================================="
echo "Запуск тестов фильтрации файлов"
echo "=========================================="
echo ""
docker exec alpaca-file-watcher python /app/tests/test_file_filter.py

echo ""
echo "=========================================="
echo "Запуск интеграционных тестов file-watcher"
echo "=========================================="
echo ""
docker exec alpaca-file-watcher python /app/tests/test_integration.py

echo ""
echo "Все тесты завершены!"
