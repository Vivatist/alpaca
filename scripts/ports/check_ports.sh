#!/bin/bash
# Скрипт для проверки доступности портов и их перезапуска
# Запускайте на УДАЛЁННОЙ машине

echo "🔍 Checking port availability..."

check_port() {
    local port=$1
    local service=$2
    
    if nc -z localhost $port 2>/dev/null; then
        echo "✅ $service (port $port) is UP"
        return 0
    else
        echo "❌ $service (port $port) is DOWN"
        return 1
    fi
}

echo ""
echo "=== Service Status ==="
check_port 8000 "Supabase Studio"
check_port 54322 "PostgreSQL (Supabase)"
check_port 8081 "File Watcher API"
check_port 8080 "Admin Backend"
check_port 11434 "Ollama"
check_port 9000 "Unstructured API"

echo ""
echo "=== Docker Services ==="
docker compose -f services/docker-compose.yml ps

echo ""
echo "💡 If Supabase Studio is down, restart it:"
echo "   docker compose -f services/docker-compose.yml restart supabase-studio"
