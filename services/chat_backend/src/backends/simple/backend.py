"""
SimpleChatBackend — основной класс бэкенда.

RAG через Pipeline + Ollama: поиск → контекст → стриминг.
"""
from typing import Iterator
from urllib.parse import quote

from logging_config import get_logger
from settings import settings
from repository import ChatRepository

from ..protocol import ChatBackend, StreamEvent, SourceInfo
from .embedder import build_embedder
from .searcher import build_searcher
from .pipeline import SimpleRAGPipeline
from .ollama import ollama_stream
from rerankers import build_reranker_from_settings

logger = get_logger("chat_backend.simple")


class SimpleChatBackend(ChatBackend):
    """
    Простой RAG бэкенд: Pipeline (search) + Ollama (generate).
    
    Контекст из документов передаётся напрямую в промпт LLM.
    
    Компоненты (создаются лениво при первом вызове):
    - repository: работа с PostgreSQL
    - embedder: генерация эмбеддингов через Ollama
    - searcher: векторный поиск через pgvector
    - pipeline: подготовка контекста для LLM
    """
    
    def __init__(self):
        self._pipeline = None
    
    @property
    def name(self) -> str:
        return "simple"
    
    def _get_pipeline(self) -> SimpleRAGPipeline:
        """Lazy initialization пайплайна."""
        if self._pipeline is None:
            repository = ChatRepository(settings.DATABASE_URL)
            embedder = build_embedder(
                base_url=settings.OLLAMA_BASE_URL,
                model=settings.OLLAMA_EMBEDDING_MODEL
            )
            searcher = build_searcher(
                embedder=embedder,
                repository=repository,
                top_k=settings.RAG_TOP_K,
                threshold=settings.RAG_SIMILARITY_THRESHOLD
            )
            
            # Реранкер (опционально, по умолчанию none)
            reranker = build_reranker_from_settings()
            
            self._pipeline = SimpleRAGPipeline(
                searcher=searcher,
                reranker=reranker
            )
            logger.info(f"✅ Simple pipeline initialized | reranker={reranker.name}")
        return self._pipeline
    
    def _build_source_info(self, chunk: dict, base_url: str) -> SourceInfo:
        """Построить SourceInfo из chunk."""
        metadata = chunk.get("metadata", {})
        file_path = metadata.get("file_path", "")
        file_name = file_path.split("/")[-1] if file_path else "unknown"
        
        encoded_path = quote(file_path, safe="")
        download_url = f"{base_url}/api/files/download?path={encoded_path}"
        
        return SourceInfo(
            file_path=file_path,
            file_name=file_name,
            chunk_index=metadata.get("chunk_index", 0),
            similarity=chunk.get("similarity", 0),
            download_url=download_url,
            title=metadata.get("title"),
            summary=metadata.get("summary"),
            category=metadata.get("category"),
            modified_at=metadata.get("modified_at"),
        )
    
    def stream(
        self,
        query: str,
        conversation_id: str | None = None,
        base_url: str = ""
    ) -> Iterator[StreamEvent]:
        """Потоковая генерация: search → metadata → LLM stream → done."""
        logger.info(f"📨 Simple stream: {query[:50]}...")
        
        try:
            pipeline = self._get_pipeline()
            
            # 1. Поиск контекста
            ctx = pipeline.prepare_context(
                query=query,
                conversation_id=conversation_id
            )
            
            # 2. Отправляем metadata
            sources = [self._build_source_info(c, base_url) for c in ctx.chunks]
            yield StreamEvent(
                type="metadata",
                data={
                    "conversation_id": ctx.conversation_id,
                    "sources": [s.to_dict() for s in sources],
                }
            )
            
            # 3. Стримим ответ LLM
            for text_chunk in ollama_stream(
                prompt=ctx.prompt,
                base_url=settings.OLLAMA_BASE_URL,
                model=settings.OLLAMA_LLM_MODEL,
                system_prompt=ctx.system_prompt
            ):
                yield StreamEvent(type="chunk", data={"content": text_chunk})
            
            # 4. Завершаем
            yield StreamEvent(type="done", data={})
            
        except Exception as e:
            logger.error(f"❌ Simple stream error: {e}")
            yield StreamEvent(type="error", data={"error": str(e)})
