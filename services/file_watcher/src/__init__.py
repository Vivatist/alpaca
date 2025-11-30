"""
File Watcher — сервис мониторинга файлов.

=== НАЗНАЧЕНИЕ ===
Docker-сервис, который:
1. Сканирует monitored_folder
2. Вычисляет SHA256 для файлов
3. Обновляет таблицу files в БД
4. Предоставляет REST API для очереди

=== КОМПОНЕНТЫ ===
- Scanner — сканер файловой системы
- PostgresFileRepository — работа с БД
- VectorSync — синхронизация векторов
- FileFilter — фильтрация по расширениям
- FileWatcherService — основной сервис

=== REST API ===
- GET /api/next-file — следующий файл для обработки
- GET /api/queue/stats — статистика очереди

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
from core.infrastructure.database.postgres import PostgresFileRepository
from vector_sync import VectorSync
from file_filter import FileFilter
from service import FileWatcherService

__all__ = ['Scanner', 'PostgresFileRepository', 'VectorSync', 'FileFilter', 'FileWatcherService']
