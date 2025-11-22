#!/bin/bash

# Скрипт для загрузки моделей в Ollama

set -e

echo "🤖 ALPACA RAG - Initialize Ollama Models"
echo "=========================================="
echo ""

# Проверка Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker not found. Please install Docker first."
    exit 1
fi

# Проверка контейнера Ollama
CONTAINER_NAME="alpaca-rag-ollama-1"

if ! docker ps | grep -q "$CONTAINER_NAME"; then
    echo "❌ Ollama container not running."
    echo "   Start it with: cd docker && docker-compose up -d ollama"
    exit 1
fi

echo "✓ Ollama container is running"
echo ""

# Загрузка моделей
echo "📥 Downloading bge-m3 embedding model..."
docker exec -it $CONTAINER_NAME ollama pull bge-m3

echo ""
echo "📥 Downloading qwen2.5:14b LLM model (this may take a while)..."
docker exec -it $CONTAINER_NAME ollama pull qwen2.5:14b

echo ""
echo "📋 Listing installed models:"
docker exec -it $CONTAINER_NAME ollama list

echo ""
echo "=========================================="
echo "✅ Models initialized successfully!"
echo ""
echo "You can now use ALPACA RAG system."
echo ""
