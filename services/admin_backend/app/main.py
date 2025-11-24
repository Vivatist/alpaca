"""FastAPI Admin Backend для Alpaca N8N

API для управления и мониторинга системы обработки документов.
Предоставляет эндпоинты для:
- Мониторинга статуса обработки файлов
- Получения статистики
- Управления конфигурацией
- Интеграции с Lovable.dev UI
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

# Кастомный ReDoc работающий по /redoc
@app.get("/redoc", include_in_schema=False)
async def redoc_custom():
    from fastapi.responses import HTMLResponse
    
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Alpaca N8N Admin API - ReDoc</title>
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
    """Статистика по файлам в file_state"""
    total: int = Field(..., description="Общее количество файлов")
    ok: int = Field(..., description="Файлы успешно обработаны")
    added: int = Field(..., description="Новые файлы ожидают обработки")
    updated: int = Field(..., description="Изменённые файлы ожидают обработки")
    processed: int = Field(..., description="Файлы в процессе обработки")
    deleted: int = Field(..., description="Удалённые файлы")
    error: int = Field(..., description="Файлы с ошибками")


class DocumentsStats(BaseModel):
    """Статистика по таблице documents"""
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
        "service": "Alpaca N8N Admin Backend",
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
# File State Endpoints
# ============================================

@app.get("/api/file-state/stats", response_model=FileStateStats, tags=["File State"])
async def get_file_state_stats():
    """Получить статистику по файлам в file_state
    
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


@app.get("/api/file-state/files", response_model=List[FileDetail], tags=["File State"])
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


@app.get("/api/file-state/queue", tags=["File State"])
async def get_processing_queue():
    """Получить текущую очередь файлов на обработку
    
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


@app.get("/api/file-state/errors", tags=["File State"])
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
# Documents Endpoints
# ============================================

@app.get("/api/documents/stats", response_model=DocumentsStats, tags=["Documents"])
async def get_documents_stats():
    """Получить статистику по таблице documents
    
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
    - N8N_WEBHOOK_URL
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
                    'MAX_HEAVY_WORKFLOWS', 'LOOP_INTERVAL', 'N8N_WEBHOOK_URL',
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
# N8N API Integration
# ============================================

N8N_BASE_URL = os.getenv("N8N_BASE_URL", "http://n8n:5678")
N8N_API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhNTY2YWZiOS0wODQxLTQzYTUtYjVmMS04ODdiOTM5MmExOWUiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwiaWF0IjoxNzYzNzQ5NzI4fQ.3QJXAI-wunSZqmbyfT8iMJVaYxtg5i_Qq2rTIrFUONw"

async def n8n_request(endpoint: str, method: str = "GET") -> Dict[str, Any]:
    """Выполнить запрос к N8N API"""
    url = f"{N8N_BASE_URL}/api/v1/{endpoint}"
    headers = {"X-N8N-API-KEY": N8N_API_KEY}
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            if method == "GET":
                response = await client.get(url, headers=headers)
            elif method == "POST":
                response = await client.post(url, headers=headers)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            response.raise_for_status()
            return response.json()
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"N8N API error: {str(e)}")


@app.get("/api/n8n/executions", tags=["N8N"])
async def get_n8n_executions(
    limit: int = Query(default=20, ge=1, le=100, description="Количество записей"),
    workflow_id: Optional[str] = Query(default=None, description="Фильтр по workflow ID")
):
    """Получить список выполнений workflows
    
    Args:
        limit: Количество записей (1-100)
        workflow_id: Опциональный фильтр по ID workflow
    
    Returns:
        Dict: Список выполнений с информацией о статусе, времени и результатах
    """
    endpoint = f"executions?limit={limit}"
    if workflow_id:
        endpoint += f"&workflowId={workflow_id}"
    
    data = await n8n_request(endpoint)
    return data


@app.get("/api/n8n/executions/{execution_id}", tags=["N8N"])
async def get_n8n_execution_details(execution_id: str):
    """Получить детальную информацию о выполнении
    
    Args:
        execution_id: ID выполнения
    
    Returns:
        Dict: Полная информация о выполнении включая данные узлов
    """
    data = await n8n_request(f"executions/{execution_id}")
    return data


@app.get("/api/n8n/health", tags=["N8N"])
async def get_n8n_health():
    """Проверить статус N8N (не требует аутентификации)
    
    Returns:
        Dict: Статус здоровья N8N
    """
    url = f"{N8N_BASE_URL}/healthz"
    
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            return {
                "status": "healthy",
                "n8n_url": N8N_BASE_URL,
                "response": response.json() if response.text else {}
            }
    except httpx.HTTPError as e:
        return {
            "status": "unhealthy",
            "n8n_url": N8N_BASE_URL,
            "error": str(e)
        }


# ============================================
# Dashboard Endpoint (для Lovable.dev)
# ============================================

@app.get("/api/dashboard", tags=["Dashboard"])
async def get_dashboard_data():
    """Получить все данные для дашборда одним запросом
    
    Агрегирует данные из всех эндпоинтов для оптимизации:
    - Статистика file_state
    - Статистика documents
    - Очередь обработки
    - Файлы с ошибками
    - Статус системы
    - N8N workflows и статус
    """
    try:
        # Получаем N8N данные параллельно, но не ломаем дашборд если N8N недоступен
        n8n_data = {}
        try:
            n8n_health = await get_n8n_health()
            n8n_data = {
                "health": n8n_health,
                "available": True
            }
        except Exception as e:
            n8n_data = {
                "available": False,
                "error": str(e)
            }
        
        return {
            "file_state": db.get_file_state_stats(),
            "documents": db.get_documents_stats(),
            "queue": db.get_processing_queue(),
            "errors": db.get_error_files(),
            "health": db.get_database_health(),
            "n8n": n8n_data
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
