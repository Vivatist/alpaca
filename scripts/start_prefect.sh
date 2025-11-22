#!/bin/bash
# Запуск Prefect server

set -e

echo "🚀 Запуск Prefect server..."
echo ""

# Проверка виртуального окружения
if [ -z "$VIRTUAL_ENV" ]; then
    echo "⚠️  Виртуальное окружение не активировано!"
    echo "   Запустите: source venv/bin/activate"
    exit 1
fi

# Загрузка переменных окружения
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
    echo "✅ Переменные окружения загружены"
else
    echo "⚠️  Файл .env не найден, используются значения по умолчанию"
fi

# Установка Prefect переменных окружения
export PREFECT_API_URL="${PREFECT_API_URL:-http://localhost:4200/api}"
export PREFECT_SERVER_API_HOST="${PREFECT_SERVER_HOST:-0.0.0.0}"
export PREFECT_SERVER_API_PORT="${PREFECT_SERVER_PORT:-4200}"
export PREFECT_LOGGING_LEVEL="${PREFECT_LOGGING_LEVEL:-INFO}"

echo ""
echo "📋 Конфигурация Prefect:"
echo "   API URL: $PREFECT_API_URL"
echo "   Host: $PREFECT_SERVER_API_HOST"
echo "   Port: $PREFECT_SERVER_API_PORT"
echo "   Log Level: $PREFECT_LOGGING_LEVEL"
echo ""

# Проверка БД (опционально - Prefect использует SQLite по умолчанию)
echo "🗄️  База данных: SQLite (по умолчанию)"
echo ""

# Запуск Prefect server
echo "🎯 Запуск Prefect server..."
echo "   UI доступен на: http://localhost:$PREFECT_SERVER_API_PORT"
echo ""

prefect server start
