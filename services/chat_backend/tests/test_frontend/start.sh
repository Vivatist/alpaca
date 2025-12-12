#!/bin/bash
# Запуск тестового фронтенда ALPACA RAG
# Использование: ./start.sh

PORT=8888
DIR="$(cd "$(dirname "$0")" && pwd)"

# Проверяем наличие Node.js
if ! command -v node &> /dev/null; then
    echo ""
    echo "  ⚠️  Node.js не найден!"
    echo "  Установите Node.js: https://nodejs.org/"
    echo ""
    echo "  Запускаем через Python (без сохранения запросов)..."
    echo ""
    sleep 2
    
    # Открываем в браузере
    if command -v xdg-open &> /dev/null; then
        xdg-open "http://127.0.0.1:$PORT" &
    elif command -v open &> /dev/null; then
        open "http://127.0.0.1:$PORT" &
    fi
    
    cd "$DIR" && python -m http.server $PORT
    exit 0
fi

echo ""
echo "  ALPACA RAG Test Console"
echo "  =========================="
echo ""
echo "  URL: http://127.0.0.1:$PORT"
echo ""
echo "  API:"
echo "  GET    /api/queries     - список запросов"
echo "  POST   /api/queries     - добавить запрос"
echo "  DELETE /api/queries/:id - удалить запрос"
echo ""
echo "  Нажмите Ctrl+C для остановки"
echo ""

# Открываем в системном браузере
if command -v xdg-open &> /dev/null; then
    xdg-open "http://127.0.0.1:$PORT" &
elif command -v open &> /dev/null; then
    open "http://127.0.0.1:$PORT" &
fi

cd "$DIR" && node server.js
