#!/bin/bash
# Entrypoint для запуска file_watcher с API и scanner сервисами

set -e

echo "Starting File Watcher services..."

# Запуск FastAPI в фоне
echo "Starting API server on port 8081..."
cd /app/src
uvicorn api:app --host 0.0.0.0 --port 8081 &
API_PID=$!

# Даем API время на запуск
sleep 2

# Запуск основного scanner процесса
echo "Starting file scanner..."
cd /app
python main.py &
SCANNER_PID=$!

# Функция для graceful shutdown
cleanup() {
    echo "Shutting down services..."
    kill $API_PID 2>/dev/null || true
    kill $SCANNER_PID 2>/dev/null || true
    wait $API_PID 2>/dev/null || true
    wait $SCANNER_PID 2>/dev/null || true
    echo "Services stopped"
    exit 0
}

# Ловим сигналы завершения
trap cleanup SIGTERM SIGINT

# Ждем завершения любого из процессов
wait -n

# Если один процесс упал, останавливаем второй
cleanup
