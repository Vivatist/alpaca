"""FastAPI Admin Backend для Alpaca

API для управления и мониторинга системы обработки документов.
Предоставляет эндпоинты для:
- Мониторинга статуса обработки файлов
- Получения статистики
- Управления конфигурацией
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
import os
import docker
import httpx

from database import Database

# Инициализация FastAPI
app = FastAPI(
    title="Alpaca Admin API",
    description="REST API для управления системой управления знаниями предприятия",
    version="1.0.0",
    docs_url="/docs",
    redoc_url=None,  # Отключаем стандартный ReDoc, используем кастомный
    openapi_url="/openapi.json",
    swagger_ui_parameters={
        "syntaxHighlight.theme": "monokai"
    }
)

# Переопределяем для генерации OpenAPI 3.0.7 вместо 3.1.0
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    
    from fastapi.openapi.utils import get_openapi
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    
    # Изменяем версию OpenAPI на 3.0.7
    openapi_schema["openapi"] = "3.0.7"
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

# Кастомный ReDoc работающий по /redoc
@app.get("/redoc", include_in_schema=False)
async def redoc_custom():
    from fastapi.responses import HTMLResponse
    
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Alpaca Admin API - ReDoc</title>
        <meta charset="utf-8"/>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body {
                margin: 0;
                padding: 0;
            }
        </style>
    </head>
    <body>
        <div id="redoc-container"></div>
        <script>
            // Встраиваем ReDoc через npm unpkg зеркало или используем fallback
            (function() {
                var script = document.createElement('script');
                script.src = 'https://unpkg.com/redoc@latest/bundles/redoc.standalone.js';
                script.onerror = function() {
                    // Fallback если unpkg недоступен
                    document.getElementById('redoc-container').innerHTML = 
                        '<div style="padding: 20px; font-family: Arial;"><h1>ReDoc недоступен</h1>' +
                        '<p>Используйте <a href="/docs">Swagger UI</a> вместо ReDoc</p></div>';
                };
                script.onload = function() {
                    Redoc.init('/openapi.json', {
                        scrollYOffset: 50
                    }, document.getElementById('redoc-container'));
                };
                document.body.appendChild(script);
            })();
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html)

# CORS для интеграции с фронтендом
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # В продакшене указать конкретные домены
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Инициализация БД
db = Database()


# ============================================
# Pydantic Models для документации API
# ============================================

class FileStateStats(BaseModel):
    """Статистика по файлам в таблице files"""
    total: int = Field(..., description="Общее количество файлов")
    ok: int = Field(..., description="Файлы успешно обработаны")
    added: int = Field(..., description="Новые файлы ожидают обработки")
    updated: int = Field(..., description="Изменённые файлы ожидают обработки")
    processed: int = Field(..., description="Файлы в процессе обработки")
    deleted: int = Field(..., description="Удалённые файлы")
    error: int = Field(..., description="Файлы с ошибками")


class DocumentsStats(BaseModel):
    """Статистика по таблице chunks"""
    total_chunks: int = Field(..., description="Общее количество чанков")
    unique_files: int = Field(..., description="Количество уникальных файлов")
    avg_chunks_per_file: float = Field(..., description="Среднее количество чанков на файл")


class ServiceConfig(BaseModel):
    """Конфигурация сервиса"""
    service_name: str = Field(..., description="Название сервиса")
    environment: Dict[str, str] = Field(..., description="Переменные окружения")


class SystemHealth(BaseModel):
    """Общее состояние системы"""
    status: str = Field(..., description="Статус: healthy/degraded/unhealthy")
    services: Dict[str, Any] = Field(..., description="Статус каждого сервиса")
    database: Dict[str, Any] = Field(..., description="Состояние базы данных")


class FileDetail(BaseModel):
    """Детальная информация о файле"""
    file_path: str
    file_size: int
    file_hash: str
    status_sync: str
    file_mtime: Optional[float]
    last_checked: Optional[str]


# ============================================
# Health Check
# ============================================

@app.get("/", tags=["Health"])
async def root():
    """Проверка доступности API"""
    return {
        "service": "Alpaca Admin Backend",
        "status": "running",
        "version": "1.0.0",
        "docs": "/docs"
    }


@app.get("/health", response_model=SystemHealth, tags=["Health"])
async def health_check():
    """Комплексная проверка состояния всей системы
    
    Проверяет:
    - Подключение к базе данных
    - Наличие pgvector расширения
    - Размеры таблиц
    """
    db_health = db.get_database_health()
    
    # Определяем общий статус
    overall_status = "healthy"
    if not db_health.get('connected'):
        overall_status = "unhealthy"
    
    return {
        "status": overall_status,
        "services": {
            "admin_backend": "healthy",
            "database": "healthy" if db_health.get('connected') else "unhealthy"
        },
        "database": db_health
    }


# ============================================
# Files Endpoints
# ============================================

@app.get("/api/files/stats", response_model=FileStateStats, tags=["Files"])
async def get_file_state_stats():
    """Получить статистику по файлам в таблице files
    
    Возвращает количество файлов в каждом статусе:
    - ok: успешно обработаны
    - added: новые, ожидают обработки
    - updated: изменённые, ожидают обработки
    - processed: в процессе обработки
    - deleted: удалённые
    - error: с ошибками
    """
    try:
        stats = db.get_file_state_stats()
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@app.get("/api/files/list", response_model=List[FileDetail], tags=["Files"])
async def get_file_state_files(
    status: Optional[str] = Query(None, description="Фильтр по статусу"),
    limit: int = Query(100, ge=1, le=1000, description="Максимальное количество записей"),
    offset: int = Query(0, ge=0, description="Смещение для пагинации")
):
    """Получить список файлов с детальной информацией
    
    Поддерживает:
    - Фильтрацию по статусу
    - Пагинацию (limit/offset)
    """
    try:
        files = db.get_file_state_details(status=status, limit=limit, offset=offset)
        return files
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@app.get("/api/files/queue", tags=["Files"])
async def get_processing_queue():
    """Получить текущий список файлов ожидающих обработку и детальную информацию
    
    Возвращает файлы со статусами: added, updated, deleted
    """
    try:
        queue = db.get_processing_queue()
        return {
            "queue": queue,
            "summary": {
                "added": len(queue['added']),
                "updated": len(queue['updated']),
                "deleted": len(queue['deleted']),
                "total": len(queue['added']) + len(queue['updated']) + len(queue['deleted'])
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@app.get("/api/files/errors", tags=["Files"])
async def get_error_files():
    """Получить список файлов со статусом error
    
    Файлы с ошибками требуют ручного вмешательства
    """
    try:
        errors = db.get_error_files()
        return {
            "errors": errors,
            "count": len(errors)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


# ============================================
# Chunks Endpoints
# ============================================

@app.get("/api/chunks/stats", response_model=DocumentsStats, tags=["Chunks"])
async def get_documents_stats():
    """Получить статистику по таблице chunks
    
    Возвращает:
    - Общее количество чанков
    - Количество уникальных файлов
    - Среднее количество чанков на файл
    """
    try:
        stats = db.get_documents_stats()
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


# ============================================
# Configuration Endpoints
# ============================================

@app.get("/api/config/file-watcher", response_model=ServiceConfig, tags=["Configuration"])
async def get_file_watcher_config():
    """Получить конфигурацию file-watcher сервиса
    
    Возвращает все переменные окружения:
    - MONITORED_PATH
    - ALLOWED_EXTENSIONS
    - SCAN_INTERVAL
    - FILE_MIN_SIZE
    - FILE_MAX_SIZE
    - EXCLUDED_DIRS
    - EXCLUDED_PATTERNS
    """
    try:
        client = docker.from_env()
        container = client.containers.get('alpaca-file-watcher')
        
        # Получаем environment переменные из контейнера
        env_list = container.attrs['Config']['Env']
        
        env_vars = {}
        for env_str in env_list:
            if '=' in env_str:
                key, value = env_str.split('=', 1)
                # Фильтруем только релевантные переменные
                if key in [
                    'MONITORED_PATH', 'ALLOWED_EXTENSIONS', 'SCAN_INTERVAL',
                    'FILE_MIN_SIZE', 'FILE_MAX_SIZE', 'EXCLUDED_DIRS',
                    'EXCLUDED_PATTERNS', 'DB_HOST', 'DB_PORT', 'DB_NAME'
                ]:
                    env_vars[key] = value
        
        return {
            "service_name": "file-watcher",
            "environment": env_vars
        }
    except docker.errors.NotFound:
        raise HTTPException(status_code=404, detail="Container 'alpaca-file-watcher' not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get config: {str(e)}")


@app.get("/api/config/main-loop", response_model=ServiceConfig, tags=["Configuration"])
async def get_main_loop_config():
    """Получить конфигурацию main-loop сервиса
    
    Возвращает все переменные окружения:
    - MAX_HEAVY_WORKFLOWS
    - LOOP_INTERVAL

    - POSTGRES_HOST
    - POSTGRES_PORT
    """
    try:
        client = docker.from_env()
        container = client.containers.get('alpaca-main-loop')
        
        # Получаем environment переменные из контейнера
        env_list = container.attrs['Config']['Env']
        
        env_vars = {}
        for env_str in env_list:
            if '=' in env_str:
                key, value = env_str.split('=', 1)
                # Фильтруем только релевантные переменные
                if key in [
                    'MAX_HEAVY_WORKFLOWS', 'LOOP_INTERVAL',
                    'POSTGRES_HOST', 'POSTGRES_PORT', 'POSTGRES_DB',
                    'POSTGRES_USER'
                ]:
                    env_vars[key] = value
        
        return {
            "service_name": "main-loop",
            "environment": env_vars
        }
    except docker.errors.NotFound:
        raise HTTPException(status_code=404, detail="Container 'alpaca-main-loop' not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get config: {str(e)}")


# ============================================
# Dashboard Endpoint (для Lovable.dev)
# ============================================

@app.get("/api/dashboard", tags=["Dashboard"])
async def get_dashboard_data():
    """Получить все данные для дашборда одним запросом
    
    Агрегирует данные из всех эндпоинтов для оптимизации:
    - Статистика files
    - Статистика chunks
    - Очередь обработки
    - Файлы с ошибками
    - Статус системы
    """
    try:
        return {
            "files": db.get_file_state_stats(),
            "chunks": db.get_documents_stats(),
            "queue": db.get_processing_queue(),
            "errors": db.get_error_files(),
            "health": db.get_database_health()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get dashboard data: {str(e)}")


# ============================================
# Error Handler
# ============================================

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Глобальный обработчик ошибок"""
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "detail": str(exc),
            "path": str(request.url)
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
