"""
Chat API endpoints.
"""
import asyncio
import json
import time
from typing import Optional, AsyncGenerator, Iterator
from urllib.parse import quote
from fastapi import APIRouter, HTTPException, Request, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from logging_config import get_logger
from pipelines import get_pipeline
from llm import generate_response, generate_response_stream
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
    # Метаданные документа
    title: str | None = None
    summary: str | None = None
    category: str | None = None
    modified_at: str | None = None


class ChatResponse(BaseModel):
    """Ответ чата."""
    answer: str
    conversation_id: str
    sources: list[SourceInfo] = []
    attachment: AttachmentInfo | None = None  # Информация о прикреплённом файле


def _build_source_info(chunk: dict, base_url: str) -> SourceInfo:
    """Построить SourceInfo из chunk с download_url и метаданными."""
    metadata = chunk.get("metadata", {})
    file_path = metadata.get("file_path", "")
    file_name = file_path.split("/")[-1] if file_path else "unknown"
    
    # URL-encode путь для безопасной передачи
    encoded_path = quote(file_path, safe="")
    download_url = f"{base_url}/api/files/download?path={encoded_path}"
    
    return SourceInfo(
        file_path=file_path,
        file_name=file_name,
        chunk_index=metadata.get("chunk_index", 0),
        similarity=chunk.get("similarity", 0),
        download_url=download_url,
        # Метаданные из чанка
        title=metadata.get("title"),
        summary=metadata.get("summary"),
        category=metadata.get("category"),
        modified_at=metadata.get("modified_at"),
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
        ctx = pipeline.prepare_context(
            query=request.message,
            conversation_id=request.conversation_id
        )
        
        # Генерируем ответ через LLM
        answer = generate_response(
            prompt=ctx.prompt,
            system_prompt=ctx.system_prompt
        )
        
        if not answer:
            answer = "Извините, не удалось сгенерировать ответ. Попробуйте позже."
        
        # Формируем base_url для ссылок
        # Используем PUBLIC_URL если задан, иначе base_url из запроса
        if settings.PUBLIC_URL:
            base_url = settings.PUBLIC_URL.rstrip("/")
        else:
            base_url = str(req.base_url).rstrip("/")
        
        return ChatResponse(
            answer=answer,
            conversation_id=ctx.conversation_id,
            sources=[_build_source_info(c, base_url) for c in ctx.chunks]
        )
        
    except Exception as e:
        logger.error(f"❌ Chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stream")
async def chat_stream(request: ChatRequest, req: Request) -> StreamingResponse:
    """
    Отправить сообщение в чат с потоковым ответом (SSE).
    
    Формат событий:
    - `event: metadata` — источники и conversation_id (отправляется первым)
    - `event: chunk` — часть ответа LLM
    - `event: done` — завершение генерации
    - `event: error` — ошибка (если произошла)
    
    Каждое событие содержит data в формате JSON.
    """
    logger.info(f"📨 Chat stream request: {request.message[:50]}...")
    
    # Формируем base_url для ссылок
    if settings.PUBLIC_URL:
        base_url = settings.PUBLIC_URL.rstrip("/")
    else:
        base_url = str(req.base_url).rstrip("/")
    
    async def event_generator() -> AsyncGenerator[str, None]:
        try:
            pipeline = get_pipeline()
            
            # 1. Подготавливаем контекст (search + prompt)
            t_start = time.time()
            ctx = pipeline.prepare_context(
                query=request.message,
                conversation_id=request.conversation_id
            )
            t_context = time.time() - t_start
            logger.info(f"⏱️ TIMING: prepare_context took {t_context:.2f}s")
            
            # 2. Отправляем metadata
            sources = [_build_source_info(c, base_url).model_dump() for c in ctx.chunks]
            data = {
                "conversation_id": ctx.conversation_id,
                "sources": sources,
            }
            yield f"event: metadata\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
            
            # 3. Стримим ответ LLM
            t_llm_start = time.time()
            first_chunk = True
            
            for text_chunk in generate_response_stream(
                prompt=ctx.prompt,
                system_prompt=ctx.system_prompt
            ):
                if first_chunk:
                    t_first_token = time.time() - t_llm_start
                    logger.info(f"⏱️ TIMING: LLM TTFT = {t_first_token:.2f}s")
                    first_chunk = False
                
                chunk_data = {"content": text_chunk}
                yield f"event: chunk\ndata: {json.dumps(chunk_data, ensure_ascii=False)}\n\n"
                
                if settings.STREAM_CHUNK_DELAY > 0:
                    await asyncio.sleep(settings.STREAM_CHUNK_DELAY)
            
            # 4. Завершаем
            t_total = time.time() - t_start
            logger.info(f"⏱️ TIMING: TOTAL = {t_total:.2f}s")
            yield f"event: done\ndata: {{}}\n\n"
        
        except Exception as e:
            logger.error(f"❌ Chat stream error: {e}")
            error_data = {"error": str(e)}
            yield f"event: error\ndata: {json.dumps(error_data, ensure_ascii=False)}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Отключаем буферизацию nginx
        }
    )


@router.post("/agent/stream")
async def agent_stream(request: ChatRequest, req: Request) -> StreamingResponse:
    """
    Агентский чат с потоковым ответом (SSE).
    
    В отличие от /stream, агент сам решает когда использовать поиск документов.
    Контекст НЕ передаётся в промпте — агент вызывает инструмент search_documents.
    
    Формат событий:
    - `event: chunk` — часть ответа агента
    - `event: done` — завершение генерации
    - `event: error` — ошибка
    """
    logger.info(f"📨 Agent stream request: {request.message[:50]}...")
    
    async def event_generator() -> AsyncGenerator[str, None]:
        try:
            from llm.langchain_agent import generate_response_stream as agent_stream_fn
            
            t_start = time.time()
            first_chunk = True
            
            # Системный промпт для агента
            system_prompt = """Ты — полезный ассистент компании ALPACA. 
У тебя есть инструмент search_documents для поиска информации в документах компании.

Правила:
1. Если вопрос требует информации из документов — используй search_documents
2. Если вопрос общий или не требует поиска — отвечай напрямую
3. НЕ выдумывай информацию о документах — ищи через инструмент
4. Отвечай на русском языке, кратко и по делу"""
            
            for text_chunk in agent_stream_fn(
                prompt=request.message,
                system_prompt=system_prompt
            ):
                if first_chunk:
                    t_first_token = time.time() - t_start
                    logger.info(f"⏱️ TIMING: Agent TTFT = {t_first_token:.2f}s")
                    first_chunk = False
                
                chunk_data = {"content": text_chunk}
                yield f"event: chunk\ndata: {json.dumps(chunk_data, ensure_ascii=False)}\n\n"
                
                if settings.STREAM_CHUNK_DELAY > 0:
                    await asyncio.sleep(settings.STREAM_CHUNK_DELAY)
            
            t_total = time.time() - t_start
            logger.info(f"⏱️ TIMING: Agent TOTAL = {t_total:.2f}s")
            yield f"event: done\ndata: {{}}\n\n"
        
        except Exception as e:
            logger.error(f"❌ Agent stream error: {e}")
            error_data = {"error": str(e)}
            yield f"event: error\ndata: {json.dumps(error_data, ensure_ascii=False)}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )
 

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
        ctx = pipeline.prepare_context(
            query=message,
            conversation_id=conversation_id
        )
        
        # Генерируем ответ через LLM
        answer = generate_response(
            prompt=ctx.prompt,
            system_prompt=ctx.system_prompt
        )
        
        if not answer:
            answer = "Извините, не удалось сгенерировать ответ. Попробуйте позже."
        
        # Формируем base_url для ссылок
        if settings.PUBLIC_URL:
            base_url = settings.PUBLIC_URL.rstrip("/")
        else:
            base_url = str(req.base_url).rstrip("/")
        
        return ChatResponse(
            answer=answer,
            conversation_id=ctx.conversation_id,
            sources=[_build_source_info(c, base_url) for c in ctx.chunks],
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
