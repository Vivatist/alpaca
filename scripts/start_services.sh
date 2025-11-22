#!/bin/bash
# Запуск внешних сервисов (Ollama + Unstructured)

set -e

echo "🚀 Запуск внешних сервисов..."
echo ""

cd "$(dirname "$0")/../docker"

# Проверка Docker
if ! docker ps > /dev/null 2>&1; then
    echo "❌ Docker не запущен!"
    exit 1
fi

# Запуск контейнеров
docker compose up -d

echo ""
echo "✅ Контейнеры запущены:"
echo "   - Ollama: http://localhost:11434"
echo "   - Unstructured: http://localhost:9000"
echo ""

# Ожидание Ollama
echo "⏳ Ожидание запуска Ollama..."
for i in {1..30}; do
    if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
        echo "✅ Ollama готов"
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
