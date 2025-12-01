"""FastAPI модуль для file_watcher

Предоставляет API эндпоинты для работы с очередью файлов.
Изолированный сервис — не зависит от core/.
"""

from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from typing import Optional, Dict
from pydantic import BaseModel, Field
import os

from repository import FileWatcherRepository

# Инициализация FastAPI
app = FastAPI(
    title="File Watcher API",
    description="API для управления очередью обработки файлов",
    version="2.0.0"
)

# Инициализация репозитория
db = FileWatcherRepository(database_url=os.getenv("DATABASE_URL"))


class FileResponse(BaseModel):
    """Модель файла для обработки"""
    path: str = Field(..., description="Путь к файлу")
    hash: str = Field(..., description="SHA256 хэш файла")
    size: int = Field(..., description="Размер файла в байтах")
    mtime: float = Field(..., description="Время модификации файла")
    status_sync: str = Field(..., description="Текущий статус файла")
    last_checked: Optional[str] = Field(None, description="Время последней проверки")


@app.get("/health")
async def health():
    """Проверка здоровья сервиса"""
    return {"status": "healthy", "service": "file-watcher-api", "version": "2.0.0"}


@app.get("/api/next-file", response_model=Optional[FileResponse])
async def get_next_file():
    """Получить следующий файл для обработки
    
    Приоритет обработки:
    1. deleted - файлы помеченные для удаления
    2. updated - измененные файлы
    3. added - новые файлы
    
    Файл атомарно помечается как 'processed' для предотвращения дублирования.
    
    Returns:
        FileResponse: Информация о следующем файле для обработки
        204 No Content: Если очередь пуста
    """
    try:
        next_file = db.get_next_file()
        
        if next_file is None:
            return Response(status_code=204)
        
        return next_file.as_dict()
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@app.get("/api/queue/stats")
async def get_queue_stats() -> Dict[str, int]:
    """Получить статистику очереди обработки
    
    Returns:
        Dict: Количество файлов по каждому статусу
    """
    try:
        return db.get_queue_stats()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
