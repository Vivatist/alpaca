@echo off
chcp 65001 >nul
REM Запуск тестового фронтенда ALPACA RAG
REM Использование: start.bat

set PORT=8888
set DIR=%~dp0

echo.
echo  ALPACA RAG Test Console
echo  ==========================
echo.
echo  URL: http://127.0.0.1:%PORT%
echo.
echo  Нажмите Ctrl+C для остановки
echo.

REM Открываем в системном браузере
start http://127.0.0.1:%PORT%

cd /d "%DIR%"
python -m http.server %PORT%
