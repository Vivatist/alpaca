@echo off
chcp 65001 >nul
REM Запуск тестового фронтенда ALPACA RAG
REM Использование: start.bat

set PORT=8888
set DIR=%~dp0

REM Проверяем наличие Node.js
where node >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo  Ошибка: Node.js не найден!
    echo  Установите Node.js: https://nodejs.org/
    echo.
    echo  Пока запускаем через Python (без сохранения запросов)...
    echo.
    timeout /t 3 >nul
    start http://127.0.0.1:%PORT%
    cd /d "%DIR%"
    python -m http.server %PORT%
    exit /b
)

echo.
echo  ALPACA RAG Test Console
echo  ==========================
echo.
echo  URL: http://127.0.0.1:%PORT%
echo.
echo  API:
echo  GET    /api/queries     - список запросов
echo  POST   /api/queries     - добавить запрос
echo  DELETE /api/queries/:id - удалить запрос
echo.
echo  Нажмите Ctrl+C для остановки
echo.

REM Открываем в системном браузере
start http://127.0.0.1:%PORT%

cd /d "%DIR%"
node server.js
