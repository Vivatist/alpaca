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
import sys
from pathlib import Path
import httpx

# Добавляем корень репозитория при локальном запуске
try:
    repo_root = Path(__file__).resolve().parents[3]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
except IndexError:
    pass

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

# Ollama URL
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434")


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


class SystemHealth(BaseModel):
    """Общее состояние системы"""
    status: str = Field(..., description="Статус: healthy/degraded/unhealthy")
    services: Dict[str, Any] = Field(..., description="Статус каждого сервиса")
    database: Dict[str, Any] = Field(..., description="Состояние базы данных")


class OllamaModel(BaseModel):
    """Информация о загруженной модели Ollama"""
    name: str = Field(..., description="Название модели")
    size_vram_mb: int = Field(..., description="Размер в VRAM (MB)")
    parameter_size: Optional[str] = Field(None, description="Размер модели (параметры)")
    quantization: Optional[str] = Field(None, description="Уровень квантизации")
    family: Optional[str] = Field(None, description="Семейство модели")


class OllamaModelsResponse(BaseModel):
    """Список загруженных моделей Ollama"""
    models: List[OllamaModel] = Field(..., description="Список загруженных моделей")
    total_vram_mb: int = Field(..., description="Общий объём VRAM (MB)")
    ollama_url: str = Field(..., description="URL Ollama сервера")


class OllamaSpeedTest(BaseModel):
    """Результат теста скорости Ollama"""
    model: str = Field(..., description="Тестируемая модель")
    prompt_tokens: int = Field(..., description="Токенов в промпте")
    generated_tokens: int = Field(..., description="Сгенерировано токенов")
    total_duration_s: float = Field(..., description="Общее время (секунды)")
    tokens_per_second: float = Field(..., description="Скорость генерации (tok/s)")
    response_preview: str = Field(..., description="Превью ответа (первые 100 символов)")


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

@app.get("/api/config", tags=["Configuration"])
async def get_system_config():
    """Получить конфигурацию системы
    
    Возвращает конфигурацию admin-backend и URL внешних сервисов.
    Значения берутся из переменных окружения контейнера.
    """
    # Маскируем пароль в DATABASE_URL
    db_url = os.getenv("DATABASE_URL", "")
    if "@" in db_url:
        # postgresql://user:password@host:port/db -> postgresql://user:***@host:port/db
        parts = db_url.split("@")
        prefix = parts[0]
        if ":" in prefix:
            user_part = prefix.rsplit(":", 1)[0]
            db_url_masked = f"{user_part}:***@{parts[1]}"
        else:
            db_url_masked = db_url
    else:
        db_url_masked = db_url
    
    return {
        "admin_backend": {
            "database_url": db_url_masked,
            "ollama_url": OLLAMA_BASE_URL,
            "timezone": os.getenv("TZ", "UTC")
        },
        "services": {
            "filewatcher": "http://filewatcher:8081",
            "chat_backend": "http://chat-backend:8000",
            "mcp_server": "http://mcp-server:8000",
            "ollama": OLLAMA_BASE_URL
        }
    }


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
    - Статус Ollama и загруженные модели
    """
    try:
        # Базовые данные из БД
        result = {
            "files": db.get_file_state_stats(),
            "chunks": db.get_documents_stats(),
            "queue": db.get_processing_queue(),
            "errors": db.get_error_files(),
            "health": db.get_database_health()
        }
        
        # Добавляем данные Ollama (не блокирует если недоступен)
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                # Загруженные модели
                ps_response = await client.get(f"{OLLAMA_BASE_URL}/api/ps")
                ps_data = ps_response.json() if ps_response.status_code == 200 else {}
                
                models = []
                total_vram = 0
                for m in ps_data.get("models", []):
                    size_vram = m.get("size_vram", 0)
                    size_vram_mb = size_vram // (1024 * 1024)
                    total_vram += size_vram_mb
                    details = m.get("details", {})
                    models.append({
                        "name": m.get("name", "unknown"),
                        "size_vram_mb": size_vram_mb,
                        "parameter_size": details.get("parameter_size"),
                        "quantization": details.get("quantization_level"),
                        "family": details.get("family")
                    })
                
                # Доступные модели
                tags_response = await client.get(f"{OLLAMA_BASE_URL}/api/tags")
                tags_data = tags_response.json() if tags_response.status_code == 200 else {}
                available_models = [m.get("name") for m in tags_data.get("models", [])]
                
                result["ollama"] = {
                    "status": "healthy",
                    "url": OLLAMA_BASE_URL,
                    "loaded_models": models,
                    "total_vram_mb": total_vram,
                    "available_models": available_models
                }
        except Exception as e:
            result["ollama"] = {
                "status": "unhealthy",
                "url": OLLAMA_BASE_URL,
                "error": str(e)
            }
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get dashboard data: {str(e)}")


# ============================================
# Ollama Endpoints
# ============================================


@app.get("/api/ollama/models", response_model=OllamaModelsResponse, tags=["Ollama"])
async def get_ollama_models():
    """Получить список загруженных моделей в VRAM
    
    Возвращает:
    - Список моделей с размером в VRAM
    - Общий объём используемой VRAM
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{OLLAMA_BASE_URL}/api/ps")
            response.raise_for_status()
            data = response.json()
            
            models = []
            total_vram = 0
            
            for m in data.get("models", []):
                size_vram = m.get("size_vram", 0)
                size_vram_mb = size_vram // (1024 * 1024)
                total_vram += size_vram_mb
                
                details = m.get("details", {})
                models.append(OllamaModel(
                    name=m.get("name", "unknown"),
                    size_vram_mb=size_vram_mb,
                    parameter_size=details.get("parameter_size"),
                    quantization=details.get("quantization_level"),
                    family=details.get("family")
                ))
            
            return OllamaModelsResponse(
                models=models,
                total_vram_mb=total_vram,
                ollama_url=OLLAMA_BASE_URL
            )
    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail=f"Cannot connect to Ollama: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get models: {str(e)}")


@app.get("/api/ollama/speed-test", response_model=OllamaSpeedTest, tags=["Ollama"])
async def test_ollama_speed(
    model: str = Query("qwen2.5:32b", description="Модель для тестирования"),
    num_predict: int = Query(50, ge=1, le=200, description="Количество токенов для генерации")
):
    """Тест скорости генерации LLM
    
    Выполняет тестовый запрос к Ollama и измеряет:
    - Время генерации
    - Скорость в токенах/секунду
    
    Нормальная скорость для RTX 3090:
    - qwen2.5:32b: 30-40 tok/s
    - Если < 5 tok/s — модель работает на CPU!
    """
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            payload = {
                "model": model,
                "prompt": "Count from 1 to 20: 1, 2, 3,",
                "stream": False,
                "options": {"num_predict": num_predict}
            }
            
            response = await client.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json=payload
            )
            response.raise_for_status()
            data = response.json()
            
            eval_count = data.get("eval_count", 0)
            eval_duration = data.get("eval_duration", 1)  # наносекунды
            total_duration = data.get("total_duration", 1)  # наносекунды
            prompt_eval_count = data.get("prompt_eval_count", 0)
            
            # Конвертируем наносекунды в секунды
            eval_duration_s = eval_duration / 1e9
            total_duration_s = total_duration / 1e9
            
            tokens_per_second = eval_count / eval_duration_s if eval_duration_s > 0 else 0
            
            return OllamaSpeedTest(
                model=model,
                prompt_tokens=prompt_eval_count,
                generated_tokens=eval_count,
                total_duration_s=round(total_duration_s, 2),
                tokens_per_second=round(tokens_per_second, 1),
                response_preview=data.get("response", "")[:100]
            )
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail=f"Ollama timeout after 120s. Model may need to load.")
    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail=f"Cannot connect to Ollama: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Speed test failed: {str(e)}")


@app.get("/api/ollama/health", tags=["Ollama"])
async def check_ollama_health():
    """Проверка доступности Ollama
    
    Возвращает:
    - Статус подключения
    - Список доступных моделей
    - URL сервера
    """
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{OLLAMA_BASE_URL}/api/tags")
            response.raise_for_status()
            data = response.json()
            
            models = [m.get("name") for m in data.get("models", [])]
            
            return {
                "status": "healthy",
                "ollama_url": OLLAMA_BASE_URL,
                "available_models": models,
                "model_count": len(models)
            }
    except httpx.RequestError as e:
        return {
            "status": "unhealthy",
            "ollama_url": OLLAMA_BASE_URL,
            "error": str(e)
        }


@app.get("/api/ollama/status", tags=["Ollama"])
async def get_ollama_status():
    """Детальный статус Ollama с метриками производительности
    
    Возвращает:
    - Загруженные модели с context_length и временем истечения
    - Latency API (индикатор нагрузки)
    - Версия Ollama
    
    Примечание: Ollama API не предоставляет CPU/GPU utilization напрямую.
    Для мониторинга GPU используйте nvidia-smi на хосте.
    """
    import time
    
    result = {
        "ollama_url": OLLAMA_BASE_URL,
        "status": "unknown",
        "version": None,
        "latency_ms": None,
        "loaded_models": [],
        "total_vram_mb": 0
    }
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Измеряем latency
            start = time.time()
            version_response = await client.get(f"{OLLAMA_BASE_URL}/api/version")
            latency_ms = int((time.time() - start) * 1000)
            result["latency_ms"] = latency_ms
            
            if version_response.status_code == 200:
                result["version"] = version_response.json().get("version")
            
            # Получаем загруженные модели с детальной информацией
            ps_response = await client.get(f"{OLLAMA_BASE_URL}/api/ps")
            if ps_response.status_code == 200:
                ps_data = ps_response.json()
                
                for m in ps_data.get("models", []):
                    size_vram = m.get("size_vram", 0)
                    size_vram_mb = size_vram // (1024 * 1024)
                    result["total_vram_mb"] += size_vram_mb
                    
                    details = m.get("details", {})
                    
                    # Парсим expires_at для показа времени до выгрузки
                    expires_at = m.get("expires_at", "")
                    
                    result["loaded_models"].append({
                        "name": m.get("name", "unknown"),
                        "size_vram_mb": size_vram_mb,
                        "context_length": m.get("context_length"),
                        "parameter_size": details.get("parameter_size"),
                        "quantization": details.get("quantization_level"),
                        "family": details.get("family"),
                        "expires_at": expires_at
                    })
            
            result["status"] = "healthy"
            
            # Добавляем рекомендацию по низкой скорости
            if latency_ms > 500:
                result["warning"] = f"High latency ({latency_ms}ms) may indicate heavy load"
            
    except httpx.RequestError as e:
        result["status"] = "unhealthy"
        result["error"] = str(e)
    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)
    
    return result


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
