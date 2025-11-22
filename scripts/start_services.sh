#!/bin/bash
# Запуск всех сервисов (Ollama, Unstructured, Prefect, Supabase)

set -e

echo "🚀 Запуск всех сервисов..."
echo ""

# Проверка Docker
if ! docker ps > /dev/null 2>&1; then
    echo "❌ Docker не запущен!"
    exit 1
fi

# Проверка установки Supabase
SUPABASE_DOCKER="/home/alpaca/supabase/docker"
if [ ! -d "$SUPABASE_DOCKER" ]; then
    echo "⚠️  Supabase не установлен"
    echo "Запуск установки Supabase..."
    "$(dirname "$0")/setup_supabase.sh"
fi

# Запуск Supabase
echo "📦 Запуск Supabase..."
cd "$SUPABASE_DOCKER"
docker compose up -d
echo "✅ Supabase запущен"
echo ""

# Запуск контейнеров проекта
echo "📦 Запуск сервисов проекта..."
cd "$(dirname "$0")/../docker"
docker compose up -d

echo ""
echo "✅ Все контейнеры запущены:"
echo ""
echo "   🗄️  Supabase:"
echo "      - Studio UI: http://localhost:8000"
echo "      - API Gateway: http://localhost:8000"
echo "      - PostgreSQL: localhost:5432 (direct), localhost:6543 (pooled)"
echo ""
echo "   📦 Сервисы проекта:"
echo "      - Ollama: http://localhost:11434"
echo "      - Unstructured: http://localhost:9000"
echo "      - Prefect UI: http://localhost:4200"
echo ""

# Ожидание PostgreSQL
echo "⏳ Ожидание запуска PostgreSQL..."
for i in {1..60}; do
    if docker exec supabase-db pg_isready -U postgres > /dev/null 2>&1; then
        echo "✅ PostgreSQL готов"
        break
    fi
    if [ $i -eq 60 ]; then
        echo "⚠️  PostgreSQL не запустился за 2 минуты"
    fi
    sleep 2
done

# Ожидание Ollama
echo "⏳ Ожидание запуска Ollama..."
for i in {1..30}; do
    if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
        echo "✅ Ollama готов"
        break
    fi
    sleep 2
done

# Ожидание Prefect
echo "⏳ Ожидание запуска Prefect..."
for i in {1..30}; do
    if curl -s http://localhost:4200/api/health > /dev/null 2>&1; then
        echo "✅ Prefect готов"
        break
    fi
    sleep 2
done

# Проверка и загрузка моделей
echo ""
echo "🤖 Проверка моделей..."

# Модель для embeddings
if ! curl -s http://localhost:11434/api/tags | grep -q "bge-m3"; then
    echo "📥 Загрузка bge-m3..."
    docker exec alpaca-rag-ollama-1 ollama pull bge-m3
else
    echo "✅ bge-m3 уже загружена"
fi

# Модель для LLM
if ! curl -s http://localhost:11434/api/tags | grep -q "qwen2.5:32b"; then
    echo "📥 Загрузка qwen2.5:32b (это займет время, ~20GB)..."
    docker exec alpaca-rag-ollama-1 ollama pull qwen2.5:32b
else
    echo "✅ qwen2.5:32b уже загружена"
fi

# Предзагрузка моделей в память
echo ""
echo "🚀 Предзагрузка моделей в GPU..."
echo "Это держит модели постоянно в памяти для быстрых ответов"

# Загружаем bge-m3 (генерируем тестовый embedding)
docker exec alpaca-rag-ollama-1 ollama run bge-m3 "test" > /dev/null 2>&1 &

# Загружаем qwen2.5:32b (генерируем тестовый ответ)  
docker exec alpaca-rag-ollama-1 ollama run qwen2.5:32b "привет" > /dev/null 2>&1 &

echo "✅ Модели загружаются в GPU (работают в фоне)"

echo ""
echo "✅ Все сервисы готовы!"
