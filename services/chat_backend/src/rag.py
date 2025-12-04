"""
RAG Service - оркестратор pipeline.

Объединяет embedder, repository и LLM для генерации ответов.
"""

from typing import List, Dict, Any, Optional
import uuid

from logging_config import get_logger
from settings import settings
from repository import ChatRepository
from embedders import build_embedder
from llm import generate_response

logger = get_logger("chat_backend.rag")


# Системный промпт для RAG
RAG_SYSTEM_PROMPT = """Ты — полезный ассистент компании ALPACA. Отвечай на вопросы пользователя, используя предоставленный контекст из документов.

Правила:
1. Отвечай ТОЛЬКО на основе предоставленного контекста
2. Если в контексте нет информации для ответа — честно скажи об этом
3. Указывай источники информации, если они известны
4. Отвечай на русском языке
5. Будь точным и конкретным"""


class RAGService:
    """Сервис RAG для генерации ответов на основе документов."""
    
    def __init__(self, repository: ChatRepository):
        self.repository = repository
        self.embedder = build_embedder()
    
    def search_context(
        self,
        query: str,
        top_k: int = None,
        threshold: float = None
    ) -> List[Dict[str, Any]]:
        """
        Поиск релевантного контекста для запроса.
        
        Args:
            query: Текст запроса
            top_k: Количество чанков (default: из settings)
            threshold: Порог схожести (default: из settings)
            
        Returns:
            Список релевантных чанков с метаданными
        """
        if top_k is None:
            top_k = settings.RAG_TOP_K
        if threshold is None:
            threshold = settings.RAG_SIMILARITY_THRESHOLD
        
        # 1. Получаем embedding запроса
        embedding = self.embedder(query)
        
        if not embedding:
            logger.warning("Failed to get embedding for query")
            return []
        
        # 2. Ищем похожие чанки
        chunks = self.repository.search_similar_chunks(
            embedding=embedding,
            limit=top_k,
            threshold=threshold
        )
        
        logger.info(f"Found {len(chunks)} relevant chunks for query")
        return chunks
    
    def build_prompt(self, query: str, chunks: List[Dict[str, Any]]) -> str:
        """
        Формирует prompt для LLM с контекстом.
        
        Args:
            query: Вопрос пользователя
            chunks: Релевантные чанки
            
        Returns:
            Готовый prompt для LLM
        """
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
        
        prompt = f"""Контекст из документов:
{context}

Вопрос пользователя: {query}

Ответ:"""
        
        return prompt
    
    def generate_answer(
        self,
        query: str,
        conversation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Полный RAG pipeline: поиск → промпт → генерация.
        
        Args:
            query: Вопрос пользователя
            conversation_id: ID разговора (для истории)
            
        Returns:
            Dict с answer, conversation_id, sources
        """
        logger.info(f"🔍 RAG query: {query[:50]}...")
        
        # 1. Поиск контекста
        chunks = self.search_context(query)
        
        # 2. Формируем промпт
        prompt = self.build_prompt(query, chunks)
        
        # 3. Генерируем ответ
        answer = generate_response(
            prompt=prompt,
            system_prompt=RAG_SYSTEM_PROMPT
        )
        
        if not answer:
            answer = "Извините, не удалось сгенерировать ответ. Попробуйте позже."
        
        # 4. Формируем источники
        sources = []
        for chunk in chunks:
            metadata = chunk.get("metadata", {})
            sources.append({
                "file_path": metadata.get("file_path", ""),
                "chunk_index": metadata.get("chunk_index", 0),
                "similarity": chunk.get("similarity", 0),
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


# Singleton instance (инициализируется при первом использовании)
_rag_service: Optional[RAGService] = None


def get_rag_service() -> RAGService:
    """Получить singleton RAG сервиса."""
    global _rag_service
    if _rag_service is None:
        repository = ChatRepository(settings.DATABASE_URL)
        _rag_service = RAGService(repository)
    return _rag_service


__all__ = [
    "RAGService",
    "get_rag_service",
]
