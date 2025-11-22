#!/bin/bash

# Скрипт для запуска Prefect worker

set -e

echo "🤖 ALPACA RAG - Start Prefect Worker"
echo "====================================="
echo ""

# Активация venv
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found. Run ./scripts/setup_dev.sh first."
    exit 1
fi

source venv/bin/activate

# Проверка Prefect
if ! command -v prefect &> /dev/null; then
    echo "❌ Prefect not installed. Installing..."
    pip install prefect>=2.14.0
fi

echo "✓ Prefect installed"
echo ""

# Настройка Prefect API
export PREFECT_API_URL="${PREFECT_API_URL:-http://127.0.0.1:4200/api}"

echo "📡 Prefect API: $PREFECT_API_URL"
echo ""

# Проверка подключения к Prefect API
echo "🔍 Checking Prefect API connection..."
if ! prefect profile ls > /dev/null 2>&1; then
    echo "⚠️  Prefect API not accessible."
    echo "   Starting local Prefect server..."
    echo ""
    echo "Run in another terminal:"
    echo "  prefect server start"
    echo ""
    echo "Or use Prefect Cloud:"
    echo "  prefect cloud login"
    echo ""
    exit 1
fi

echo "✓ Connected to Prefect API"
echo ""

# Создание work pool если нет
echo "📋 Ensuring work pool exists..."
prefect work-pool create default --type process > /dev/null 2>&1 || true
echo "✓ Work pool 'default' ready"
echo ""

# Запуск worker
echo "🚀 Starting Prefect worker..."
echo ""
echo "Worker will process flows from 'default' work queue."
echo "Press Ctrl+C to stop."
echo ""

prefect worker start --pool default
