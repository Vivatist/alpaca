#!/bin/bash
# Остановка внешних сервисов (Ollama + Unstructured + Prefect)

set -e

echo "🛑 Остановка внешних сервисов..."
echo ""

cd "$(dirname "$0")/../docker"

# Проверка Docker
if ! docker ps > /dev/null 2>&1; then
    echo "❌ Docker не запущен!"
    exit 1
fi

# Остановка контейнеров
docker compose down

echo ""
echo "✅ Все сервисы остановлены"
echo ""
echo "💡 Для полной очистки (включая volumes) используйте:"
echo "   docker compose down -v"
