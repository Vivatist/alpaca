"""FastAPI модуль для file_watcher

Предоставляет API эндпоинты для работы с очередью файлов
"""

from fastapi import FastAPI, HTTPException
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
import os
import sys
from pathlib import Path

# Добавляем корень репозитория если запускаем локально вне Docker
try:
    repo_root = Path(__file__).resolve().parents[3]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
except IndexError:
    pass

from core.infrastructure.database.postgres import PostgresFileRepository
from core.application.files import DequeueNextFile, GetQueueStats

# Инициализация FastAPI
app = FastAPI(
    title="File Watcher API",
    description="API для управления очередью обработки файлов",
    version="1.0.0"
)

# Инициализация БД и use-case
db = PostgresFileRepository(database_url=os.getenv("DATABASE_URL"))
dequeue_next_file = DequeueNextFile(db)
get_queue_stats_use_case = GetQueueStats(db)


class FileResponse(BaseModel):
    """Модель файла для обработки"""
    path: str = Field(..., description="Путь к файлу")
    hash: str = Field(..., description="SHA256 хэш файла")
    size: int = Field(..., description="Размер файла в байтах")
    status_sync: str = Field(..., description="Текущий статус файла")
    last_checked: Optional[str] = Field(None, description="Время последней проверки")


@app.get("/health")
async def health():
    """Проверка здоровья сервиса"""
    return {"status": "healthy", "service": "file-watcher-api"}


@app.get("/api/next-file", response_model=Optional[FileResponse])
async def get_next_file():
    """Получить следующий файл для обработки
    
    Приоритет обработки:
    1. deleted - файлы помеченные для удаления
    2. updated - измененные файлы
    3. added - новые файлы
    
    Внутри каждой группы выбирается файл с самым ранним временем изменения статуса (last_checked).
    
    Returns:
        FileResponse: Информация о следующем файле для обработки
        None: Если очередь пуста (возвращает 204 No Content)
    """
    try:
        next_file = dequeue_next_file()
        
        if next_file is None:
            # Очередь пуста - возвращаем 204 No Content
            from fastapi.responses import Response
            return Response(status_code=204)
        
        return next_file.as_dict()
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@app.get("/api/queue/stats")
async def get_queue_stats():
    """Получить статистику очереди обработки
    
    Returns:
        Dict: Количество файлов по каждому статусу
    """
    try:
        stats = get_queue_stats_use_case()
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
