"""
Simple Chat Backend — RAG через Pipeline + Ollama.

Использует существующий SimplePipeline для поиска,
Ollama для генерации ответов.
"""
from typing import Iterator
from urllib.parse import quote

from logging_config import get_logger
from pipelines import get_pipeline
from llm import generate_response, generate_response_stream

from .protocol import ChatBackend, StreamEvent, SourceInfo, ChatResult

logger = get_logger("chat_backend.backends.simple")


class SimpleChatBackend(ChatBackend):
    """
    Простой RAG бэкенд: Pipeline (search) + Ollama (generate).
    
    Контекст из документов передаётся напрямую в промпт LLM.
    """
    
    @property
    def name(self) -> str:
        return "simple"
    
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
        """
        Потоковая генерация: search → metadata event → LLM stream → done.
        """
        logger.info(f"📨 Simple stream: {query[:50]}...")
        
        try:
            pipeline = get_pipeline()
            
            # 1. Подготавливаем контекст (поиск)
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
            for text_chunk in generate_response_stream(
                prompt=ctx.prompt,
                system_prompt=ctx.system_prompt
            ):
                yield StreamEvent(type="chunk", data={"content": text_chunk})
            
            # 4. Завершаем
            yield StreamEvent(type="done", data={})
            
        except Exception as e:
            logger.error(f"❌ Simple stream error: {e}")
            yield StreamEvent(type="error", data={"error": str(e)})
    
    def chat(
        self,
        query: str,
        conversation_id: str | None = None,
        base_url: str = ""
    ) -> ChatResult:
        """
        Синхронная генерация: search → LLM → result.
        """
        logger.info(f"📨 Simple chat: {query[:50]}...")
        
        pipeline = get_pipeline()
        
        ctx = pipeline.prepare_context(
            query=query,
            conversation_id=conversation_id
        )
        
        answer = generate_response(
            prompt=ctx.prompt,
            system_prompt=ctx.system_prompt
        )
        
        if not answer:
            answer = "Извините, не удалось сгенерировать ответ. Попробуйте позже."
        
        sources = [self._build_source_info(c, base_url) for c in ctx.chunks]
        
        return ChatResult(
            answer=answer,
            conversation_id=ctx.conversation_id,
            sources=sources
        )
