"""
File Watcher — изолированный сервис мониторинга файлов.

=== НАЗНАЧЕНИЕ ===
Docker-сервис, который:
1. Сканирует monitored_folder
2. Вычисляет SHA256 для файлов
3. Обновляет таблицу files в БД
4. Предоставляет REST API для очереди

=== ИЗОЛЯЦИЯ ===
Сервис НЕ зависит от core/ — использует локальный repository.py
с собственной реализацией SQL-запросов.

=== КОМПОНЕНТЫ ===
- Scanner — сканер файловой системы
- FileWatcherRepository — работа с БД (локальная реализация)
- VectorSync — синхронизация векторов
- FileFilter — фильтрация по расширениям
- FileWatcherService — основной сервис

=== REST API ===
- GET /api/next-file — следующий файл для обработки
- GET /api/queue/stats — статистика очереди
- GET /health — проверка здоровья

=== ПОРТ ===
http://localhost:8081

=== ЗАПУСК ===
    cd ~/alpaca/services && docker compose up -d filewatcher

=== ПРИОРИТЕТЫ ОБРАБОТКИ ===
1. deleted — удалённые файлы
2. updated — изменённые
3. added — новые
"""

from scanner import Scanner
from repository import FileWatcherRepository
from vector_sync import VectorSync
from file_filter import FileFilter
from service import FileWatcherService

__all__ = ['Scanner', 'FileWatcherRepository', 'VectorSync', 'FileFilter', 'FileWatcherService']
