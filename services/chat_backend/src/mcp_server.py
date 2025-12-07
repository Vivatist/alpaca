"""
MCP Server для ALPACA RAG - инструменты поиска документов.

Model Context Protocol (MCP) сервер предоставляет инструменты для:
- Поиска документов в базе знаний
- Получения информации о документе по пути

Запуск:
    python mcp_server.py

Или через uvicorn:
    uvicorn mcp_server:app --host 0.0.0.0 --port 8083
"""

import os
import sys
from typing import List, Dict, Any, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI
from pydantic import BaseModel, Field

# Добавляем путь к src для импортов
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from logging_config import setup_logging, get_logger
from settings import settings
from repository import ChatRepository
from embedders import build_embedder
from vector_searchers import build_searcher

setup_logging()
logger = get_logger("mcp_server")


# === Pydantic Models ===

class SearchRequest(BaseModel):
    """Запрос на поиск документов."""
    query: str = Field(..., description="Поисковый запрос на естественном языке")
    top_k: int = Field(default=5, ge=1, le=20, description="Количество результатов")
    threshold: float = Field(default=0.3, ge=0.0, le=1.0, description="Минимальный порог релевантности")


class DocumentChunk(BaseModel):
    """Фрагмент документа."""
    content: str
    file_path: str
    file_name: str
    chunk_index: int
    similarity: float
    title: Optional[str] = None
    summary: Optional[str] = None
    category: Optional[str] = None


class SearchResponse(BaseModel):
    """Ответ на поиск."""
    query: str
    chunks: List[DocumentChunk]
    total_found: int


class ToolDefinition(BaseModel):
    """Определение инструмента для MCP."""
    name: str
    description: str
    parameters: Dict[str, Any]


class MCPToolsResponse(BaseModel):
    """Список доступных инструментов."""
    tools: List[ToolDefinition]


# === Singleton components ===

_repository: Optional[ChatRepository] = None
_searcher = None


def get_repository() -> ChatRepository:
    global _repository
    if _repository is None:
        _repository = ChatRepository(settings.DATABASE_URL)
    return _repository


def get_searcher():
    global _searcher
    if _searcher is None:
        repository = get_repository()
        embedder = build_embedder()
        _searcher = build_searcher(embedder, repository)
    return _searcher


# === FastAPI App ===

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager."""
    logger.info("🚀 MCP Server starting...")
    # Инициализируем компоненты при старте
    get_searcher()
    logger.info("✅ MCP Server ready")
    yield
    logger.info("👋 MCP Server shutting down")


app = FastAPI(
    title="ALPACA MCP Server",
    description="Model Context Protocol сервер для поиска документов",
    version="1.0.0",
    lifespan=lifespan,
)


# === MCP Endpoints ===

@app.get("/health")
async def health():
    """Health check."""
    return {"status": "healthy", "service": "ALPACA MCP Server"}


@app.get("/tools", response_model=MCPToolsResponse)
async def list_tools():
    """
    Список доступных инструментов (MCP tools/list).
    
    Возвращает определения инструментов в формате JSON Schema.
    """
    return MCPToolsResponse(tools=[
        ToolDefinition(
            name="search_documents",
            description="Поиск релевантных документов в базе знаний компании ALPACA. "
                       "Используй для ответов на вопросы о договорах, документах, процедурах.",
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Поисковый запрос на естественном языке"
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Количество результатов (1-20)",
                        "default": 5
                    }
                },
                "required": ["query"]
            }
        ),
        ToolDefinition(
            name="get_document_info",
            description="Получить информацию о конкретном документе по пути к файлу.",
            parameters={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Путь к файлу относительно базовой директории"
                    }
                },
                "required": ["file_path"]
            }
        ),
    ])


@app.post("/tools/search_documents", response_model=SearchResponse)
async def search_documents(request: SearchRequest):
    """
    Поиск документов в базе знаний (MCP tools/call).
    
    Выполняет семантический поиск по векторной базе данных.
    Возвращает релевантные фрагменты документов с метаданными.
    """
    logger.info(f"🔍 Search request: {request.query[:50]}...")
    
    searcher = get_searcher()
    
    # Выполняем поиск
    raw_chunks = searcher.search(
        query=request.query,
        top_k=request.top_k,
        threshold=request.threshold
    )
    
    # Преобразуем в response model
    chunks = []
    for chunk in raw_chunks:
        metadata = chunk.get("metadata", {})
        file_path = metadata.get("file_path", "")
        
        chunks.append(DocumentChunk(
            content=chunk.get("content", ""),
            file_path=file_path,
            file_name=file_path.split("/")[-1] if file_path else "unknown",
            chunk_index=metadata.get("chunk_index", 0),
            similarity=chunk.get("similarity", 0),
            title=metadata.get("title"),
            summary=metadata.get("summary"),
            category=metadata.get("category"),
        ))
    
    logger.info(f"✅ Found {len(chunks)} chunks for query: {request.query[:30]}...")
    
    return SearchResponse(
        query=request.query,
        chunks=chunks,
        total_found=len(chunks)
    )


@app.post("/tools/get_document_info")
async def get_document_info(file_path: str):
    """
    Получить информацию о документе (MCP tools/call).
    
    Возвращает все чанки документа с метаданными.
    """
    logger.info(f"📄 Document info request: {file_path}")
    
    repository = get_repository()
    
    # Ищем чанки по file_path
    chunks = repository.get_chunks_by_file_path(file_path)
    
    if not chunks:
        return {"error": f"Document not found: {file_path}"}
    
    # Собираем метаданные из первого чанка
    first_chunk = chunks[0]
    metadata = first_chunk.get("metadata", {})
    
    return {
        "file_path": file_path,
        "file_name": file_path.split("/")[-1] if file_path else "unknown",
        "title": metadata.get("title"),
        "summary": metadata.get("summary"),
        "category": metadata.get("category"),
        "total_chunks": len(chunks),
        "chunks_preview": [
            {
                "chunk_index": c.get("metadata", {}).get("chunk_index", i),
                "content_preview": c.get("content", "")[:200] + "..."
            }
            for i, c in enumerate(chunks[:5])  # Первые 5 чанков
        ]
    }


# === Simplified MCP Call Endpoint ===

class MCPCallRequest(BaseModel):
    """Универсальный запрос вызова инструмента."""
    tool: str = Field(..., description="Имя инструмента")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="Аргументы")


@app.post("/call")
async def mcp_call(request: MCPCallRequest):
    """
    Универсальный endpoint для вызова инструментов (MCP-style).
    
    Пример:
    ```json
    {
        "tool": "search_documents",
        "arguments": {"query": "договор аренды", "top_k": 3}
    }
    ```
    """
    if request.tool == "search_documents":
        search_req = SearchRequest(**request.arguments)
        return await search_documents(search_req)
    
    elif request.tool == "get_document_info":
        file_path = request.arguments.get("file_path", "")
        return await get_document_info(file_path)
    
    else:
        return {"error": f"Unknown tool: {request.tool}"}


# === Main ===

if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("MCP_PORT", "8083"))
    uvicorn.run(app, host="0.0.0.0", port=port)
