#!/bin/bash
# Скрипт для запуска ALPACA RAG системы

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Цвета
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}╔════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║     ALPACA RAG - Система запуска      ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════╝${NC}"
echo ""

# 1. Проверка .env
if [ ! -f ".env" ]; then
    echo -e "${RED}❌ Файл .env не найден!${NC}"
    echo ""
    echo "Создаю .env из .env.example..."
    cp .env.example .env
    echo -e "${YELLOW}⚠️  ВАЖНО: Отредактируйте .env файл и укажите:${NC}"
    echo "   - DATABASE_URL (PostgreSQL connection string)"
    echo "   - MONITORED_PATH (путь к папке с документами)"
    echo ""
    read -p "Нажмите Enter когда настроите .env..."
fi

# 2. Активация venv
echo -e "${YELLOW}📦 Активация виртуального окружения...${NC}"
if [ ! -d "venv" ]; then
    echo -e "${RED}❌ Виртуальное окружение не найдено!${NC}"
    echo "Создаю venv..."
    python3.13 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
else
    source venv/bin/activate
fi
echo -e "${GREEN}✅ venv активирован${NC}"
echo ""

# 3. Проверка Docker сервисов
echo -e "${YELLOW}🐳 Проверка Docker сервисов...${NC}"
if ! docker ps > /dev/null 2>&1; then
    echo -e "${RED}❌ Docker не запущен!${NC}"
    echo "Запустите Docker Desktop или docker daemon"
    exit 1
fi

cd docker
if ! docker-compose ps | grep -q "Up"; then
    echo "Запускаю Docker сервисы (Ollama + Unstructured)..."
    docker-compose up -d
    echo "Ожидание запуска сервисов (30 сек)..."
    sleep 30
fi
cd ..
echo -e "${GREEN}✅ Docker сервисы запущены${NC}"
echo ""

# 4. Проверка Ollama моделей
echo -e "${YELLOW}🤖 Проверка Ollama моделей...${NC}"
if ! curl -s http://localhost:11434/api/tags | grep -q "qwen2.5:14b"; then
    echo "Загружаю модель qwen2.5:14b (это займет время)..."
    ./scripts/init_models.sh
fi
echo -e "${GREEN}✅ Ollama модели готовы${NC}"
echo ""

# 5. Инициализация базы данных
echo -e "${YELLOW}🗄️  Инициализация базы данных...${NC}"
python -c "
import asyncio
from app.db.connection import init_db

async def main():
    try:
        await init_db()
        print('✅ База данных инициализирована')
    except Exception as e:
        print(f'❌ Ошибка инициализации БД: {e}')
        print('Проверьте DATABASE_URL в .env файле')
        exit(1)

asyncio.run(main())
" || exit 1
echo ""

# 6. Создание папки для мониторинга
echo -e "${YELLOW}📁 Проверка папки мониторинга...${NC}"
MONITORED_PATH=$(python -c "from settings import settings; print(settings.MONITORED_PATH)")
if [ ! -d "$MONITORED_PATH" ]; then
    echo "Создаю папку: $MONITORED_PATH"
    mkdir -p "$MONITORED_PATH"
fi
echo -e "${GREEN}✅ Папка мониторинга: $MONITORED_PATH${NC}"
echo ""

# 7. Запуск компонентов
echo -e "${GREEN}╔════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║         Запуск компонентов             ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════╝${NC}"
echo ""

echo "Для работы системы нужно запустить 3 компонента в разных терминалах:"
echo ""
echo -e "${YELLOW}Терминал 1 - FastAPI сервер:${NC}"
echo "   cd $SCRIPT_DIR && source venv/bin/activate"
echo "   uvicorn main:app --reload --host 0.0.0.0 --port 8000"
echo ""
echo -e "${YELLOW}Терминал 2 - Prefect Server (опционально):${NC}"
echo "   cd $SCRIPT_DIR && source venv/bin/activate"
echo "   prefect server start"
echo ""
echo -e "${YELLOW}Терминал 3 - Prefect Worker (обработка документов):${NC}"
echo "   cd $SCRIPT_DIR && source venv/bin/activate"
echo "   python scripts/deploy_flows.py"
echo ""
echo "════════════════════════════════════════"
echo ""
echo "Выберите вариант запуска:"
echo "  1) Запустить только FastAPI (без автообработки)"
echo "  2) Запустить FastAPI + Prefect flows (полная система)"
echo "  3) Показать команды и выйти"
echo ""
read -p "Ваш выбор (1-3): " choice

case $choice in
    1)
        echo ""
        echo -e "${GREEN}🚀 Запускаю FastAPI сервер...${NC}"
        echo ""
        exec uvicorn main:app --reload --host 0.0.0.0 --port 8000
        ;;
    2)
        echo ""
        echo -e "${GREEN}🚀 Запускаю полную систему...${NC}"
        echo ""
        
        # Запуск FastAPI в фоне
        uvicorn main:app --host 0.0.0.0 --port 8000 > logs/fastapi.log 2>&1 &
        FASTAPI_PID=$!
        echo -e "${GREEN}✅ FastAPI запущен (PID: $FASTAPI_PID)${NC}"
        echo "   Логи: tail -f logs/fastapi.log"
        echo "   API: http://localhost:8000"
        echo "   Docs: http://localhost:8000/docs"
        echo ""
        
        # Ожидание запуска FastAPI
        sleep 3
        
        # Запуск Prefect flows
        echo -e "${GREEN}🚀 Запускаю Prefect flows...${NC}"
        echo ""
        python scripts/deploy_flows.py
        
        # При завершении - остановить FastAPI
        echo ""
        echo "Останавливаю сервисы..."
        kill $FASTAPI_PID
        ;;
    3)
        echo ""
        echo "Команды для ручного запуска сохранены выше."
        echo "Используйте их для запуска в отдельных терминалах."
        ;;
    *)
        echo "Неверный выбор"
        exit 1
        ;;
esac
