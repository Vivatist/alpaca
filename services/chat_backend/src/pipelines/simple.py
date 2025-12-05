"""
Simple RAG Pipeline.

Простой RAG пайплайн: поиск → промпт.
Без истории диалога, без реранкинга.
"""

from typing import List, Dict, Any, Optional
import uuid

from logging_config import get_logger

from .base import BasePipeline, RAGContext

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
    
    Отвечает за RAG логику:
    1. Поиск релевантных чанков через searcher
    2. Формирование промпта с контекстом
    
    LLM вызов (sync/stream) делается в API слое.
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
    
    def prepare_context(
        self,
        query: str,
        conversation_id: Optional[str] = None,
        **kwargs
    ) -> RAGContext:
        """
        Подготавливает контекст для RAG генерации.
        
        Выполняет:
        1. Поиск релевантных чанков
        2. Формирование промпта
        3. Генерацию conversation_id
        """
        logger.info(f"🔍 RAG query: {query[:50]}...")
        
        # 1. Поиск контекста
        chunks = self.searcher.search(query)
        
        # 2. Формируем промпт
        prompt = self.build_prompt(query, chunks)
        
        # 3. Генерируем conversation_id если не передан
        if not conversation_id:
            conversation_id = str(uuid.uuid4())
        
        logger.info(f"✅ RAG context prepared | chunks={len(chunks)}")
        
        return RAGContext(
            chunks=chunks,
            prompt=prompt,
            conversation_id=conversation_id,
            system_prompt=self.system_prompt,
        )


__all__ = ["SimpleRAGPipeline", "DEFAULT_SYSTEM_PROMPT"]
