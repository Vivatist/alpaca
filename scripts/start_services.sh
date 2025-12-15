#!/bin/bash
# Запуск сервисов для локальной разработки (Supabase + ALPACA)
# Ollama работает на удалённом сервере через Tailscale

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "🚀 Запуск сервисов для разработки..."
echo ""

# Проверка Docker
if ! docker ps > /dev/null 2>&1; then
    echo "❌ Docker не запущен!"
    exit 1
fi

# Определение пути Supabase (Windows/Linux)
if [ -d "$HOME/supabase/docker" ]; then
    SUPABASE_DOCKER="$HOME/supabase/docker"
elif [ -d "/c/Users/$USER/supabase/docker" ]; then
    SUPABASE_DOCKER="/c/Users/$USER/supabase/docker"
else
    echo "⚠️  Supabase не найден"
    echo "Запустите: ./scripts/setup_supabase/setup_supabase.sh"
    exit 1
fi

# Запуск Supabase
echo "📦 Запуск Supabase..."
cd "$SUPABASE_DOCKER"
docker compose up -d
echo "✅ Supabase запущен"
echo ""

# Запуск сервисов ALPACA
echo "📦 Запуск сервисов ALPACA..."
cd "$PROJECT_DIR/services"
docker compose up -d
echo "✅ ALPACA сервисы запущены"

echo ""
echo "✅ Все контейнеры запущены:"
echo ""
echo "   🗄️  Supabase:"
echo "      - Studio UI: http://localhost:8000"
echo "      - PostgreSQL: supabase-db:5432 (внутри Docker network)"
echo ""
echo "   📦 ALPACA сервисы:"
echo "      - Admin Backend: http://localhost:8080"
echo "      - Chat Backend: http://localhost:8082"
echo "      - FileWatcher: http://localhost:8081"
echo "      - MCP Server: http://localhost:8083"
echo ""
echo "   🤖 Ollama (удалённый сервер через Tailscale):"
echo "      - URL: см. OLLAMA_BASE_URL в services/.env"
echo ""

# Ожидание PostgreSQL
echo "⏳ Ожидание запуска PostgreSQL..."
for i in {1..30}; do
    if docker exec supabase-db pg_isready -U postgres > /dev/null 2>&1; then
        echo "✅ PostgreSQL готов"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "⚠️  PostgreSQL не запустился за 1 минуту"
    fi
    sleep 2
done

# Проверка health endpoints
echo ""
echo "🔍 Проверка сервисов..."
sleep 5

for service in "localhost:8080/health:Admin" "localhost:8082/health:Chat" "localhost:8081/health:FileWatcher"; do
    url=$(echo $service | cut -d: -f1-2)
    name=$(echo $service | cut -d: -f3)
    if curl -s "http://$url" > /dev/null 2>&1; then
        echo "✅ $name Backend готов"
    else
        echo "⏳ $name Backend запускается..."
    fi
done

echo ""
echo "✅ Готово к разработке!"
