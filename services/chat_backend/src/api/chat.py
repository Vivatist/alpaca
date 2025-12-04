"""
Chat API endpoints.
"""
from typing import Optional
from urllib.parse import quote
from fastapi import APIRouter, HTTPException, Request, UploadFile, File, Form
from pydantic import BaseModel

from logging_config import get_logger
from pipelines import get_pipeline
from settings import settings

logger = get_logger("chat_backend.api.chat")

router = APIRouter(prefix="/chat", tags=["Chat"], redirect_slashes=True)

# Максимальный размер файла (10 MB)
MAX_FILE_SIZE = 10 * 1024 * 1024


class ChatRequest(BaseModel):
    """Запрос к чату (JSON)."""
    message: str
    conversation_id: str | None = None


class AttachmentInfo(BaseModel):
    """Информация о прикреплённом файле."""
    filename: str
    size: int
    content_type: str | None


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
    attachment: AttachmentInfo | None = None  # Информация о прикреплённом файле


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


@router.post("", response_model=ChatResponse)
@router.post("/", response_model=ChatResponse, include_in_schema=False)
async def chat(request: ChatRequest, req: Request) -> ChatResponse:
    """
    Отправить сообщение в чат с RAG (JSON).
    
    Pipeline:
    1. Получить embedding запроса через Ollama
    2. Найти релевантные чанки в pgvector
    3. Сформировать prompt с контекстом
    4. Отправить в LLM (Ollama)
    5. Вернуть ответ с источниками и ссылками на скачивание
    """
    logger.info(f"📨 Chat request: {request.message[:50]}...")
    
    try:
        pipeline = get_pipeline()
        result = pipeline.generate_answer(
            query=request.message,
            conversation_id=request.conversation_id
        )
        
        # Формируем base_url для ссылок
        # Используем PUBLIC_URL если задан, иначе base_url из запроса
        if settings.PUBLIC_URL:
            base_url = settings.PUBLIC_URL.rstrip("/")
        else:
            base_url = str(req.base_url).rstrip("/")
        
        return ChatResponse(
            answer=result["answer"],
            conversation_id=result["conversation_id"],
            sources=[_build_source_info(s, base_url) for s in result["sources"]]
        )
        
    except Exception as e:
        logger.error(f"❌ Chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/with-file", response_model=ChatResponse)
async def chat_with_file(
    req: Request,
    message: str = Form(..., description="Текст сообщения"),
    conversation_id: Optional[str] = Form(None, description="ID разговора"),
    file: Optional[UploadFile] = File(None, description="Прикреплённый файл (опционально)")
) -> ChatResponse:
    """
    Отправить сообщение в чат с прикреплённым файлом.
    
    Файл пока не обрабатывается (заглушка), но информация о нём возвращается.
    В будущем файл будет использоваться как дополнительный контекст к вопросу.
    
    Поддерживаемые форматы: DOCX, PDF, TXT, XLSX, PPTX
    Максимальный размер: 10 MB
    """
    logger.info(f"📨 Chat request with file: {message[:50]}...")
    
    attachment_info = None
    
    # Обрабатываем прикреплённый файл (пока только логируем)
    if file and file.filename:
        # Проверяем размер
        contents = await file.read()
        file_size = len(contents)
        
        if file_size > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=413,
                detail=f"Файл слишком большой. Максимум: {MAX_FILE_SIZE // (1024*1024)} MB"
            )
        
        attachment_info = AttachmentInfo(
            filename=file.filename,
            size=file_size,
            content_type=file.content_type
        )
        
        logger.info(f"📎 Attachment: {file.filename} ({file_size} bytes, {file.content_type})")
        
        # TODO: В будущем здесь будет:
        # 1. Парсинг файла (extract text)
        # 2. Добавление текста в контекст запроса
        # 3. Или поиск похожих документов по эмбеддингу файла
        
        # Сбрасываем позицию файла для возможного дальнейшего использования
        await file.seek(0)
    
    try:
        pipeline = get_pipeline()
        result = pipeline.generate_answer(
            query=message,
            conversation_id=conversation_id
        )
        
        # Формируем base_url для ссылок
        if settings.PUBLIC_URL:
            base_url = settings.PUBLIC_URL.rstrip("/")
        else:
            base_url = str(req.base_url).rstrip("/")
        
        return ChatResponse(
            answer=result["answer"],
            conversation_id=result["conversation_id"],
            sources=[_build_source_info(s, base_url) for s in result["sources"]],
            attachment=attachment_info
        )
        
    except Exception as e:
        logger.error(f"❌ Chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def stats():
    """Статистика базы знаний."""
    try:
        pipeline = get_pipeline()
        return {
            "total_chunks": pipeline.repository.get_total_chunks_count(),
            "unique_files": pipeline.repository.get_unique_files_count(),
        }
    except Exception as e:
        logger.error(f"Stats error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
