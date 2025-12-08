"""
RAG Pipeline для Simple Backend.

Подготавливает контекст для LLM: поиск → форматирование промпта.
"""
import uuid
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Protocol

from logging_config import get_logger

logger = get_logger("chat_backend.simple.pipeline")


# === Contracts ===

class Searcher(Protocol):
    """Протокол поисковика."""
    def search(self, query: str) -> List[Any]:
        ...


@dataclass
class RAGContext:
    """Контекст для RAG-генерации."""
    chunks: List[Dict[str, Any]]
    prompt: str
    conversation_id: str
    system_prompt: Optional[str] = None


# === Pipeline ===

class SimpleRAGPipeline:
    """
    Простой RAG пайплайн: поиск → форматирование → контекст.
    
    Не генерирует ответ, только подготавливает промпт с контекстом.
    """
    
    DEFAULT_SYSTEM_PROMPT = """Ты — полезный ассистент компании ALPACA. 
Отвечай на вопросы пользователей, используя предоставленный контекст из документов.
Если в контексте нет информации для ответа — честно скажи об этом.
Отвечай на русском языке, кратко и по делу."""
    
    CONTEXT_TEMPLATE = """Контекст из документов:

{context}

---

Вопрос пользователя: {query}"""
    
    def __init__(
        self,
        searcher: Searcher,
        system_prompt: Optional[str] = None
    ):
        self.searcher = searcher
        self.system_prompt = system_prompt or self.DEFAULT_SYSTEM_PROMPT
    
    def prepare_context(
        self,
        query: str,
        conversation_id: Optional[str] = None
    ) -> RAGContext:
        """
        Подготовить контекст для генерации.
        
        Args:
            query: Вопрос пользователя
            conversation_id: ID беседы (генерируется если не указан)
            
        Returns:
            RAGContext с чанками, промптом и системным промптом
        """
        conv_id = conversation_id or str(uuid.uuid4())
        
        # 1. Поиск релевантных чанков
        search_results = self.searcher.search(query)
        
        # 2. Преобразуем в dict для совместимости
        chunks = []
        for r in search_results:
            chunks.append({
                "content": r.content,
                "metadata": r.metadata,
                "similarity": r.similarity,
            })
        
        # 3. Форматируем контекст
        if chunks:
            context_parts = []
            for i, chunk in enumerate(chunks, 1):
                meta = chunk.get("metadata", {})
                title = meta.get("title") or meta.get("file_name") or meta.get("file_path", "")
                content = chunk.get("content", "")
                similarity = chunk.get("similarity", 0)
                context_parts.append(f"[{i}] {title} ({similarity:.2f})\n{content}")
            
            context_text = "\n\n".join(context_parts)
        else:
            context_text = "(документы не найдены)"
        
        # 4. Формируем промпт
        prompt = self.CONTEXT_TEMPLATE.format(context=context_text, query=query)
        
        logger.debug(f"Prepared context: {len(chunks)} chunks, {len(prompt)} chars")
        
        return RAGContext(
            chunks=chunks,
            prompt=prompt,
            conversation_id=conv_id,
            system_prompt=self.system_prompt
        )
