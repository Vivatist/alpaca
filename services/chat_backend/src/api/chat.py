"""
Chat API endpoints.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from logging_config import get_logger

logger = get_logger("chat_backend.api.chat")

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    """Запрос к чату."""
    message: str
    conversation_id: str | None = None


class ChatResponse(BaseModel):
    """Ответ чата."""
    answer: str
    conversation_id: str
    sources: list[dict] = []


@router.post("/", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """
    Отправить сообщение в чат.
    
    TODO: Реализовать RAG pipeline:
    1. Получить embedding запроса
    2. Найти релевантные чанки в pgvector
    3. Сформировать prompt с контекстом
    4. Отправить в LLM
    5. Вернуть ответ с источниками
    """
    logger.info(f"📨 Chat request: {request.message[:50]}...")
    
    # Hello World заглушка
    return ChatResponse(
        answer=f"Hello! Вы написали: {request.message}",
        conversation_id=request.conversation_id or "new-conversation-id",
        sources=[]
    )


@router.get("/hello")
async def hello():
    """Hello World endpoint."""
    return {"message": "Hello from ALPACA Chat Backend! 🦙"}
