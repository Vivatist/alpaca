"""
Files API - скачивание исходных документов.
"""
import os
from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from urllib.parse import unquote

from logging_config import get_logger
from settings import settings

logger = get_logger("chat_backend.api.files")

router = APIRouter(prefix="/files", tags=["Files"])

# Базовая папка с документами (монтируется в контейнер)
MONITORED_PATH = os.getenv("MONITORED_PATH", "/monitored_folder")


def _safe_path(file_path: str) -> Path:
    """
    Безопасное разрешение пути - защита от path traversal.
    
    Args:
        file_path: Относительный путь к файлу
        
    Returns:
        Абсолютный путь внутри MONITORED_PATH
        
    Raises:
        HTTPException: Если путь выходит за пределы MONITORED_PATH
    """
    # Декодируем URL-encoded путь
    file_path = unquote(file_path)
    
    # Нормализуем базовый путь
    base = Path(MONITORED_PATH).resolve()
    
    # Собираем полный путь и нормализуем
    full_path = (base / file_path).resolve()
    
    # Проверяем что путь внутри базовой директории
    if not str(full_path).startswith(str(base)):
        logger.warning(f"⚠️ Path traversal attempt: {file_path}")
        raise HTTPException(status_code=403, detail="Access denied")
    
    return full_path


@router.get("/download")
async def download_file(path: str):
    """
    Скачать файл по относительному пути.
    
    Args:
        path: Относительный путь к файлу (как в metadata.file_path)
        
    Returns:
        Файл для скачивания
        
    Example:
        GET /api/files/download?path=Георезонанс/устав.docx
    """
    try:
        full_path = _safe_path(path)
        
        if not full_path.exists():
            logger.warning(f"File not found: {path}")
            raise HTTPException(status_code=404, detail="File not found")
        
        if not full_path.is_file():
            raise HTTPException(status_code=400, detail="Not a file")
        
        # Определяем имя файла для скачивания
        filename = full_path.name
        
        logger.info(f"📥 Download: {path}")
        
        return FileResponse(
            path=full_path,
            filename=filename,
            media_type="application/octet-stream"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Download error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/preview")
async def preview_file(path: str):
    """
    Получить информацию о файле без скачивания.
    
    Args:
        path: Относительный путь к файлу
        
    Returns:
        Информация о файле (имя, размер, тип)
    """
    try:
        full_path = _safe_path(path)
        
        if not full_path.exists():
            raise HTTPException(status_code=404, detail="File not found")
        
        stat = full_path.stat()
        
        return {
            "name": full_path.name,
            "path": path,
            "size": stat.st_size,
            "size_human": _format_size(stat.st_size),
            "extension": full_path.suffix.lower(),
            "exists": True,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Preview error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _format_size(size: int) -> str:
    """Форматирование размера файла."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"
