"""
Chat API endpoints.
"""
from urllib.parse import quote
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from logging_config import get_logger
from rag import get_rag_service

logger = get_logger("chat_backend.api.chat")

router = APIRouter(prefix="/chat", tags=["Chat"])


class ChatRequest(BaseModel):
    """Запрос к чату."""
    message: str
    conversation_id: str | None = None


class SourceInfo(BaseModel):
    """Информация об источнике."""
    file_path: str
    file_name: str
    chunk_index: int
    similarity: float
    download_url: str


class ChatResponse(BaseModel):
    """Ответ чата."""
    answer: str
    conversation_id: str
    sources: list[SourceInfo] = []


def _build_source_info(source: dict, base_url: str) -> SourceInfo:
    """Построить SourceInfo с download_url."""
    file_path = source.get("file_path", "")
    file_name = file_path.split("/")[-1] if file_path else "unknown"
    
    # URL-encode путь для безопасной передачи
    encoded_path = quote(file_path, safe="")
    download_url = f"{base_url}/api/files/download?path={encoded_path}"
    
    return SourceInfo(
        file_path=file_path,
        file_name=file_name,
        chunk_index=source.get("chunk_index", 0),
        similarity=source.get("similarity", 0),
        download_url=download_url
    )


@router.post("/", response_model=ChatResponse)
async def chat(request: ChatRequest, req: Request) -> ChatResponse:
    """
    Отправить сообщение в чат с RAG.
    
    Pipeline:
    1. Получить embedding запроса через Ollama
    2. Найти релевантные чанки в pgvector
    3. Сформировать prompt с контекстом
    4. Отправить в LLM (Ollama)
    5. Вернуть ответ с источниками и ссылками на скачивание
    """
    logger.info(f"📨 Chat request: {request.message[:50]}...")
    
    try:
        rag = get_rag_service()
        result = rag.generate_answer(
            query=request.message,
            conversation_id=request.conversation_id
        )
        
        # Формируем base_url для ссылок
        # В проде это будет https://api.alpaca-smart.com:8443/chat
        base_url = str(req.base_url).rstrip("/")
        
        return ChatResponse(
            answer=result["answer"],
            conversation_id=result["conversation_id"],
            sources=[_build_source_info(s, base_url) for s in result["sources"]]
        )
        
    except Exception as e:
        logger.error(f"❌ Chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def stats():
    """Статистика базы знаний."""
    try:
        rag = get_rag_service()
        return {
            "total_chunks": rag.repository.get_total_chunks_count(),
            "unique_files": rag.repository.get_unique_files_count(),
        }
    except Exception as e:
        logger.error(f"Stats error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
