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


# === Request Model ===

class ChatRequest(BaseModel):
    """Запрос к чату (JSON)."""
    message: str
    conversation_id: str | None = None
    backend: str | None = None  # simple | agent


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

@router.post("")
@router.post("/", include_in_schema=False)
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
    
    # Backend из body или query param или default
    backend_name = request.backend or backend
    chat_backend = get_backend(backend_name) if backend_name else get_default_backend()
    actual_backend = chat_backend.name
    logger.info(f"🔧 Using backend: {actual_backend}")
    
    base_url = _get_base_url(req)
    
    async def event_generator() -> AsyncGenerator[str, None]:
        try:
            t_start = time.time()
            first_chunk = True
            ttft_sent = False
            
            for event in chat_backend.stream(
                query=request.message,
                conversation_id=request.conversation_id,
                base_url=base_url
            ):
                # Отправляем TTFT при первом chunk
                if event.type == "chunk" and first_chunk:
                    ttft = time.time() - t_start
                    logger.info(f"⏱️ TIMING: TTFT = {ttft:.2f}s")
                    first_chunk = False
                    
                    # Отправляем timing event клиенту
                    if not ttft_sent:
                        timing_event = StreamEvent(
                            type="timing",
                            data={"backend": actual_backend, "ttft": round(ttft, 2)}
                        )
                        yield _format_sse_event(timing_event)
                        ttft_sent = True
                
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


# === Stats ===

@router.get("/stats")
async def stats():
    """Статистика базы знаний."""
    try:
        from repository import ChatRepository
        repository = ChatRepository(settings.DATABASE_URL)
        return {
            "total_chunks": repository.get_total_chunks_count(),
            "unique_files": repository.get_unique_files_count(),
        }
    except Exception as e:
        logger.error(f"Stats error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
