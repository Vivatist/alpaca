"""
Chat API endpoints.

Единый интерфейс для фронтенда.
Бэкенд (simple/agent) выбирается через ENV CHAT_BACKEND или query param.
"""
import asyncio
import json
import time
from typing import Optional, AsyncGenerator
from fastapi import APIRouter, HTTPException, Request, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from logging_config import get_logger
from backends import get_backend, get_default_backend, StreamEvent
from settings import settings

logger = get_logger("chat_backend.api.chat")

router = APIRouter(prefix="/chat", tags=["Chat"], redirect_slashes=True)


# === Request/Response Models ===

class ChatRequest(BaseModel):
    """Запрос к чату (JSON)."""
    message: str
    conversation_id: str | None = None


class SourceInfo(BaseModel):
    """Информация об источнике."""
    file_path: str
    file_name: str
    chunk_index: int
    similarity: float
    download_url: str
    title: str | None = None
    summary: str | None = None
    category: str | None = None
    modified_at: str | None = None


class ChatResponse(BaseModel):
    """Ответ чата."""
    answer: str
    conversation_id: str
    sources: list[SourceInfo] = []


# === Helpers ===

def _get_base_url(req: Request) -> str:
    """Получить base_url для ссылок на скачивание."""
    if settings.PUBLIC_URL:
        return settings.PUBLIC_URL.rstrip("/")
    return str(req.base_url).rstrip("/")


def _format_sse_event(event: StreamEvent) -> str:
    """Форматирует StreamEvent в SSE."""
    return f"event: {event.type}\ndata: {json.dumps(event.data, ensure_ascii=False)}\n\n"


# === Endpoints ===

@router.post("", response_model=ChatResponse)
@router.post("/", response_model=ChatResponse, include_in_schema=False)
async def chat(
    request: ChatRequest,
    req: Request,
    backend: Optional[str] = Query(None, description="Backend: simple | agent")
) -> ChatResponse:
    """
    Отправить сообщение в чат (синхронный ответ).
    
    Backend можно указать через:
    - Query param: ?backend=agent
    - ENV: CHAT_BACKEND=agent
    """
    logger.info(f"📨 Chat request: {request.message[:50]}...")
    
    try:
        chat_backend = get_backend(backend) if backend else get_default_backend()
        base_url = _get_base_url(req)
        
        result = chat_backend.chat(
            query=request.message,
            conversation_id=request.conversation_id,
            base_url=base_url
        )
        
        return ChatResponse(
            answer=result.answer,
            conversation_id=result.conversation_id,
            sources=[
                SourceInfo(
                    file_path=s.file_path,
                    file_name=s.file_name,
                    chunk_index=s.chunk_index,
                    similarity=s.similarity,
                    download_url=s.download_url,
                    title=s.title,
                    summary=s.summary,
                    category=s.category,
                    modified_at=s.modified_at,
                )
                for s in result.sources
            ]
        )
        
    except Exception as e:
        logger.error(f"❌ Chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stream")
async def chat_stream(
    request: ChatRequest,
    req: Request,
    backend: Optional[str] = Query(None, description="Backend: simple | agent")
) -> StreamingResponse:
    """
    Отправить сообщение в чат с потоковым ответом (SSE).
    
    Backend можно указать через:
    - Query param: ?backend=agent
    - ENV: CHAT_BACKEND=agent
    
    Формат событий:
    - `event: metadata` — источники и conversation_id
    - `event: chunk` — часть ответа
    - `event: tool_call` — вызов инструмента (только agent)
    - `event: done` — завершение
    - `event: error` — ошибка
    """
    logger.info(f"📨 Chat stream request: {request.message[:50]}...")
    
    chat_backend = get_backend(backend) if backend else get_default_backend()
    base_url = _get_base_url(req)
    
    async def event_generator() -> AsyncGenerator[str, None]:
        try:
            t_start = time.time()
            first_chunk = True
            
            for event in chat_backend.stream(
                query=request.message,
                conversation_id=request.conversation_id,
                base_url=base_url
            ):
                # Логируем TTFT
                if event.type == "chunk" and first_chunk:
                    t_first_token = time.time() - t_start
                    logger.info(f"⏱️ TIMING: TTFT = {t_first_token:.2f}s")
                    first_chunk = False
                
                yield _format_sse_event(event)
                
                # Небольшая задержка для плавности (если настроено)
                if event.type == "chunk" and settings.STREAM_CHUNK_DELAY > 0:
                    await asyncio.sleep(settings.STREAM_CHUNK_DELAY)
            
            t_total = time.time() - t_start
            logger.info(f"⏱️ TIMING: TOTAL = {t_total:.2f}s")
        
        except Exception as e:
            logger.error(f"❌ Chat stream error: {e}")
            error_event = StreamEvent(type="error", data={"error": str(e)})
            yield _format_sse_event(error_event)
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


# === Deprecated endpoints (для обратной совместимости) ===

@router.post("/agent/stream", deprecated=True)
async def agent_stream_deprecated(
    request: ChatRequest,
    req: Request
) -> StreamingResponse:
    """
    DEPRECATED: Используйте POST /stream?backend=agent
    
    Сохранён для обратной совместимости.
    """
    logger.warning("⚠️ Deprecated endpoint /agent/stream called, use /stream?backend=agent")
    return await chat_stream(request, req, backend="agent")


# === Stats ===

@router.get("/stats")
async def stats():
    """Статистика базы знаний."""
    try:
        from pipelines import get_pipeline
        pipeline = get_pipeline()
        return {
            "total_chunks": pipeline.repository.get_total_chunks_count(),
            "unique_files": pipeline.repository.get_unique_files_count(),
        }
    except Exception as e:
        logger.error(f"Stats error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/backends")
async def list_backends():
    """Список доступных бэкендов."""
    from backends import BACKENDS
    return {
        "default": settings.CHAT_BACKEND,
        "available": list(BACKENDS.keys()),
    }
