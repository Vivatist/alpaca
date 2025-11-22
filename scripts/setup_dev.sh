#!/bin/bash

# Скрипт для настройки dev окружения ALPACA RAG

set -e

echo "🚀 ALPACA RAG - Setup Development Environment"
echo "=============================================="
echo ""

# Проверка Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found. Please install Python 3.12+"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1-2)
echo "✓ Python version: $PYTHON_VERSION"

# Создание venv если нет
if [ ! -d "venv" ]; then
    echo ""
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
    echo "✓ Virtual environment created"
fi

# Активация venv
echo ""
echo "🔌 Activating virtual environment..."
source venv/bin/activate

# Обновление pip
echo ""
echo "⬆️  Upgrading pip..."
pip install --upgrade pip > /dev/null

# Установка зависимостей
echo ""
echo "📥 Installing dependencies..."
pip install -r requirements.txt

echo ""
echo "✓ All dependencies installed"

# Проверка .env файла
if [ ! -f ".env" ]; then
    echo ""
    echo "⚠️  .env file not found. Creating from .env.example..."
    cp .env.example .env
    echo "✓ .env file created. Please edit it with your settings."
fi

# Проверка Docker
if ! command -v docker &> /dev/null; then
    echo ""
    echo "⚠️  Docker not found. Please install Docker to run external services."
else
    echo ""
    echo "✓ Docker installed"
fi

# Создание monitored_folder
if [ ! -d "/home/alpaca/monitored_folder" ]; then
    echo ""
    echo "📁 Creating monitored folder..."
    mkdir -p /home/alpaca/monitored_folder
    echo "✓ Monitored folder created at /home/alpaca/monitored_folder"
fi

echo ""
echo "=============================================="
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "1. Edit .env file with your settings (especially DATABASE_URL)"
echo "2. Start external services: cd docker && docker-compose up -d"
echo "3. Load Ollama models: docker exec -it alpaca-rag-ollama-1 ollama pull bge-m3"
echo "4. Run the application: python main.py"
echo ""
echo "Or use: uvicorn main:app --reload --host 0.0.0.0 --port 8000"
echo ""
