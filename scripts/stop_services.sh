#!/bin/bash
# Остановка всех сервисов (ALPACA + Supabase)

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "🛑 Остановка всех сервисов..."
echo ""

# Проверка Docker
if ! docker ps > /dev/null 2>&1; then
    echo "❌ Docker не запущен!"
    exit 1
fi

# Остановка сервисов ALPACA
echo "Остановка сервисов ALPACA..."
cd "$PROJECT_DIR/services"
docker compose down
echo "✅ ALPACA остановлен"

# Определение пути Supabase (Windows/Linux)
if [ -d "$HOME/supabase/docker" ]; then
    SUPABASE_DOCKER="$HOME/supabase/docker"
elif [ -d "/c/Users/$USER/supabase/docker" ]; then
    SUPABASE_DOCKER="/c/Users/$USER/supabase/docker"
fi

# Остановка Supabase
if [ -n "$SUPABASE_DOCKER" ] && [ -d "$SUPABASE_DOCKER" ]; then
    echo "Остановка Supabase..."
    cd "$SUPABASE_DOCKER"
    docker compose down
    echo "✅ Supabase остановлен"
fi

echo ""
echo "✅ Все сервисы остановлены"
echo ""
echo "💡 Для полной очистки (включая volumes) используйте:"
echo "   cd ~/alpaca/services && docker compose down -v"
echo "   cd ~/supabase/docker && docker compose down -v"
