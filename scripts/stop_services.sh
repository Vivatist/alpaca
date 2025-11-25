#!/bin/bash
# Остановка всех сервисов (Alpaca + Supabase)

set -e

echo "🛑 Остановка всех сервисов..."
echo ""

# Проверка Docker
if ! docker ps > /dev/null 2>&1; then
    echo "❌ Docker не запущен!"
    exit 1
fi

# Остановка сервисов проекта
echo "Остановка сервисов проекта..."
cd "$(dirname "$0")/../docker"
docker compose down

# Остановка Supabase
SUPABASE_DOCKER="/home/alpaca/supabase/docker"
if [ -d "$SUPABASE_DOCKER" ]; then
    echo "Остановка Supabase..."
    cd "$SUPABASE_DOCKER"
    docker compose down
fi

echo ""
echo "✅ Все сервисы остановлены"
echo ""
echo "💡 Для полной очистки (включая volumes) используйте:"
echo "   cd ~/alpaca/docker && docker compose down -v"
echo "   cd ~/supabase/docker && docker compose down -v"
