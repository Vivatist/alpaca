#!/bin/bash
# Запуск тестового фронтенда ALPACA RAG
# Использование: ./start.sh

PORT=8888
DIR="$(cd "$(dirname "$0")" && pwd)"

echo ""
echo "  ALPACA RAG Test Console"
echo "  =========================="
echo ""
echo "  URL: http://127.0.0.1:$PORT"
echo ""
echo "  Нажмите Ctrl+C для остановки"
echo ""

# Открываем в системном браузере
if command -v xdg-open &> /dev/null; then
    xdg-open "http://127.0.0.1:$PORT" &
elif command -v open &> /dev/null; then
    open "http://127.0.0.1:$PORT" &
fi

cd "$DIR" && python -m http.server $PORT
