#!/bin/bash
# Скрипт для проверки всех компонентов системы

set -e

echo "🔍 Проверка компонентов Alpaca RAG"
echo "===================================="
echo ""

# Активация venv
source venv/bin/activate

# Цвета для вывода
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

check_service() {
    local name=$1
    local url=$2
    
    echo -n "Проверка $name... "
    
    if curl -s --max-time 5 "$url" > /dev/null 2>&1; then
        echo -e "${GREEN}✅ OK${NC}"
        return 0
    else
        echo -e "${RED}❌ FAILED${NC}"
        return 1
    fi
}

# 1. Проверка Python модулей
echo "📦 Проверка Python модулей"
echo "-------------------------"

python -c "from app.core.file_watcher import FileScanner; print('✅ file_watcher')" || echo "❌ file_watcher"
python -c "from app.core.parser import DocumentParser; print('✅ parser')" || echo "❌ parser"
python -c "from app.core.chunker import TextChunker; print('✅ chunker')" || echo "❌ chunker"
python -c "from app.core.embedder import Embedder; print('✅ embedder')" || echo "❌ embedder"
python -c "from app.core.rag import RAGSystem; print('✅ rag')" || echo "❌ rag"
python -c "from app.db.connection import Database; print('✅ database')" || echo "❌ database"
python -c "from app.api.documents import router; print('✅ documents API')" || echo "❌ documents API"
python -c "from app.api.search import router; print('✅ search API')" || echo "❌ search API"
python -c "from app.api.admin import router; print('✅ admin API')" || echo "❌ admin API"
python -c "from app.workers.file_processor import process_document_flow; print('✅ file_processor')" || echo "❌ file_processor"
python -c "from app.workers.scheduler import file_watcher_flow; print('✅ scheduler')" || echo "❌ scheduler"
python -c "from main import app; print('✅ main application')" || echo "❌ main application"

echo ""

# 2. Проверка внешних сервисов
echo "🌐 Проверка внешних сервисов"
echo "----------------------------"

check_service "Ollama" "http://localhost:11434/api/tags" || OLLAMA_DOWN=1
check_service "Unstructured" "http://localhost:8001" || UNSTRUCTURED_DOWN=1

echo ""

# 3. Проверка базы данных
echo "🗄️  Проверка базы данных"
echo "------------------------"

python -c "
import asyncio
from app.db.connection import Database

async def check_db():
    try:
        db = Database()
        conn = await db.get_connection()
        result = await conn.fetchval('SELECT 1')
        await conn.close()
        print('✅ PostgreSQL connection OK')
        return True
    except Exception as e:
        print(f'❌ PostgreSQL connection FAILED: {e}')
        return False

asyncio.run(check_db())
" || DB_DOWN=1

echo ""

# 4. Проверка конфигурации
echo "⚙️  Проверка конфигурации"
echo "------------------------"

if [ -f ".env" ]; then
    echo "✅ .env файл найден"
else
    echo "❌ .env файл не найден"
    ENV_MISSING=1
fi

python -c "
from settings import settings
print(f'✅ APP_NAME: {settings.APP_NAME}')
print(f'✅ VERSION: {settings.VERSION}')
print(f'✅ ENVIRONMENT: {settings.ENVIRONMENT}')
print(f'✅ MONITORED_PATH: {settings.MONITORED_PATH}')
print(f'✅ CHUNK_SIZE: {settings.CHUNK_SIZE}')
print(f'✅ OLLAMA_MODEL: {settings.OLLAMA_MODEL}')
print(f'✅ OLLAMA_EMBEDDING_MODEL: {settings.OLLAMA_EMBEDDING_MODEL}')
"

echo ""

# 5. Запуск тестов
echo "🧪 Запуск тестов"
echo "---------------"

pytest tests/test_chunker.py -v

echo ""

# Итоговый отчет
echo "===================================="
echo "📊 Итоговый отчет"
echo "===================================="
echo ""

if [ -z "$OLLAMA_DOWN" ] && [ -z "$UNSTRUCTURED_DOWN" ] && [ -z "$DB_DOWN" ] && [ -z "$ENV_MISSING" ]; then
    echo -e "${GREEN}✅ Все компоненты работают корректно!${NC}"
    echo ""
    echo "Для запуска системы:"
    echo "  1. FastAPI: uvicorn main:app --reload"
    echo "  2. Prefect server: prefect server start"
    echo "  3. Deploy flows: python scripts/deploy_flows.py"
    echo "  4. Prefect worker: ./scripts/start_prefect_worker.sh"
else
    echo -e "${RED}❌ Обнаружены проблемы:${NC}"
    [ ! -z "$OLLAMA_DOWN" ] && echo "  - Ollama не доступен"
    [ ! -z "$UNSTRUCTURED_DOWN" ] && echo "  - Unstructured не доступен"
    [ ! -z "$DB_DOWN" ] && echo "  - База данных не доступна"
    [ ! -z "$ENV_MISSING" ] && echo "  - Отсутствует .env файл"
    echo ""
    echo "Проверьте docker-compose сервисы:"
    echo "  cd docker && docker-compose up -d"
fi

echo ""
