"""
Simple RAG Pipeline.

Простой RAG пайплайн: поиск → промпт → генерация.
Без истории диалога, без реранкинга.
"""

from typing import List, Dict, Any, Optional, Iterator
import uuid

from logging_config import get_logger
from contracts import Embedder, Repository
from llm import generate_response, generate_response_stream

from .base import BasePipeline

logger = get_logger("chat_backend.pipelines.simple")


# Системный промпт по умолчанию
DEFAULT_SYSTEM_PROMPT = """Ты — полезный ассистент компании ALPACA. Отвечай на вопросы пользователя, используя предоставленный контекст из документов.

Правила:
1. Отвечай ТОЛЬКО на основе предоставленного контекста
2. Если в контексте нет информации для ответа — честно скажи об этом
3. НЕ перечисляй источники в тексте ответа — они будут добавлены автоматически отдельно
4. Отвечай на русском языке
5. Будь точным и конкретным"""


class SimpleRAGPipeline(BasePipeline):
    """
    Простой RAG pipeline без истории и реранкинга.
    
    Этапы:
    1. Поиск релевантных чанков через searcher
    2. Формирование промпта с контекстом
    3. Генерация ответа через LLM
    """
    
    def __init__(
        self,
        searcher,
        repository=None,
        system_prompt: str = DEFAULT_SYSTEM_PROMPT
    ):
        """
        Args:
            searcher: Searcher для поиска релевантных чанков
            repository: Репозиторий для доступа к БД (опционально)
            system_prompt: Системный промпт для LLM
        """
        self.searcher = searcher
        self.repository = repository
        self.system_prompt = system_prompt
    
    def build_prompt(self, query: str, chunks: List[Dict[str, Any]]) -> str:
        """Формирует prompt для LLM с контекстом."""
        if not chunks:
            context = "Контекст не найден. Отвечай на основе общих знаний, но укажи, что информация не из документов компании."
        else:
            context_parts = []
            for i, chunk in enumerate(chunks, 1):
                source = chunk.get("metadata", {}).get("file_path", "неизвестный источник")
                similarity = chunk.get("similarity", 0)
                content = chunk.get("content", "")
                context_parts.append(
                    f"[Источник {i}: {source} (релевантность: {similarity:.2f})]\n{content}"
                )
            context = "\n\n".join(context_parts)
        
        return f"""Контекст из документов:
{context}

Вопрос пользователя: {query}

Ответ:"""
    
    def generate_answer(
        self,
        query: str,
        conversation_id: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Полный RAG pipeline: поиск → промпт → генерация.
        """
        logger.info(f"🔍 RAG query: {query[:50]}...")
        
        # 1. Поиск контекста
        chunks = self.searcher.search(query)
        
        # 2. Формируем промпт
        prompt = self.build_prompt(query, chunks)
        
        # 3. Генерируем ответ
        answer = generate_response(
            prompt=prompt,
            system_prompt=self.system_prompt
        )
        
        if not answer:
            answer = "Извините, не удалось сгенерировать ответ. Попробуйте позже."
        
        # 4. Формируем источники с метаданными
        sources = []
        for chunk in chunks:
            metadata = chunk.get("metadata", {})
            sources.append({
                "file_path": metadata.get("file_path", ""),
                "chunk_index": metadata.get("chunk_index", 0),
                "similarity": chunk.get("similarity", 0),
                # Метаданные документа
                "title": metadata.get("title"),
                "summary": metadata.get("summary"),
                "category": metadata.get("category"),
                "modified_at": metadata.get("modified_at"),
            })
        
        # 5. Генерируем conversation_id если не передан
        if not conversation_id:
            conversation_id = str(uuid.uuid4())
        
        logger.info(f"✅ RAG response generated | sources={len(sources)}")
        
        return {
            "answer": answer,
            "conversation_id": conversation_id,
            "sources": sources,
        }
    
    def generate_answer_stream(
        self,
        query: str,
        conversation_id: Optional[str] = None,
        **kwargs
    ) -> Iterator[Dict[str, Any]]:
        """
        Потоковый RAG pipeline: поиск → промпт → генерация (stream).
        
        Yields:
            Сначала метаданные (sources), затем части ответа (chunks)
        """
        logger.info(f"🔍 RAG stream query: {query[:50]}...")
        
        # 1. Поиск контекста (не streaming)
        chunks = self.searcher.search(query)
        
        # 2. Формируем промпт
        prompt = self.build_prompt(query, chunks)
        
        # 3. Генерируем conversation_id если не передан
        if not conversation_id:
            conversation_id = str(uuid.uuid4())
        
        # 4. Формируем источники с метаданными
        sources = []
        for chunk in chunks:
            metadata = chunk.get("metadata", {})
            sources.append({
                "file_path": metadata.get("file_path", ""),
                "chunk_index": metadata.get("chunk_index", 0),
                "similarity": chunk.get("similarity", 0),
                "title": metadata.get("title"),
                "summary": metadata.get("summary"),
                "category": metadata.get("category"),
                "modified_at": metadata.get("modified_at"),
            })
        
        # 5. Сначала отправляем метаданные (sources и conversation_id)
        yield {
            "type": "metadata",
            "conversation_id": conversation_id,
            "sources": sources,
        }
        
        # 6. Затем стримим части ответа
        for text_chunk in generate_response_stream(
            prompt=prompt,
            system_prompt=self.system_prompt
        ):
            yield {
                "type": "chunk",
                "content": text_chunk,
            }
        
        # 7. Отправляем финальное событие
        yield {
            "type": "done",
        }
        
        logger.info(f"✅ RAG stream completed | sources={len(sources)}")


__all__ = ["SimpleRAGPipeline", "DEFAULT_SYSTEM_PROMPT"]
