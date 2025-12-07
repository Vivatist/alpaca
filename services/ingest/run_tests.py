#!/usr/bin/env python3
"""
Запуск тестов Ingest Service.

Использование:
    python run_tests.py           # Все тесты
    python run_tests.py -k chunk  # Только тесты с 'chunk' в имени
    python run_tests.py -v        # Verbose режим
"""
import subprocess
import sys
from pathlib import Path

def main():
    # Переходим в директорию сервиса
    service_dir = Path(__file__).parent
    
    # Формируем команду pytest
    cmd = [sys.executable, "-m", "pytest"]
    cmd.extend(sys.argv[1:])  # Передаём аргументы
    
    # Запускаем
    result = subprocess.run(cmd, cwd=service_dir)
    sys.exit(result.returncode)

if __name__ == "__main__":
    main()
