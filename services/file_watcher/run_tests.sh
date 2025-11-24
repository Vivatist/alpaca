#!/bin/bash
# Скрипт для запуска всех тестов file-watcher

set -e

# Переходим в корень проекта
cd "$(dirname "$0")/../.."

# Проверяем что контейнер с БД запущен
if ! docker ps | grep -q supabase-db; then
    echo "ОШИБКА: Контейнер supabase-db не запущен"
    echo "Запустите: cd docker && docker compose up -d"
    exit 1
fi

# Активируем виртуальное окружение если есть
if [ -d "venv" ]; then
    source venv/bin/activate
fi

echo "=========================================="
echo "Запуск тестов фильтрации файлов"
echo "=========================================="
echo ""
python app/file_watcher/tests/test_file_filter.py

echo ""
echo "=========================================="
echo "Запуск интеграционных тестов file-watcher"
echo "=========================================="
echo ""
python app/file_watcher/tests/test_integration.py

echo ""
echo "Все тесты завершены!"
