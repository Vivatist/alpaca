"""
ComplexAgentBackend — реализация ChatBackend для complex_agent.

Интегрирует RagAgent с протоколом ChatBackend для использования
в API chat-backend сервиса.
"""
from typing import Iterator, List
from urllib.parse import quote

from logging_config import get_logger
from settings import settings

from ..protocol import ChatBackend, StreamEvent, SourceInfo
from .vector_store import VectorStoreAdapter
from .agent import RagAgent
from .schemas import SearchResult

logger = get_logger("chat_backend.complex_agent")


class ComplexAgentBackend(ChatBackend):
    """
    Complex Agent Backend — Agentic RAG с robust search и реранкингом.
    
    Особенности:
    - Извлечение фильтров из запроса через LLM
    - Итеративный поиск с ослаблением фильтров (robust_search)
    - Комбинированный реранкинг (similarity + freshness + category)
    - Промежуточные сообщения о ходе поиска
    - Streaming генерации ответа
    """
    
    def __init__(self):
        self._agent: RagAgent | None = None
        self._vector_store: VectorStoreAdapter | None = None
    
    @property
    def name(self) -> str:
        return "complex_agent"
    
    def _get_vector_store(self) -> VectorStoreAdapter:
        """Lazy initialization vector store."""
        if self._vector_store is None:
            self._vector_store = VectorStoreAdapter(
                database_url=settings.DATABASE_URL,
                table_name="chunks"
            )
            logger.info("✅ VectorStoreAdapter initialized")
        return self._vector_store
    
    def _get_agent(self) -> RagAgent:
        """Lazy initialization агента."""
        if self._agent is None:
            self._agent = RagAgent(
                vector_store=self._get_vector_store(),
                ollama_url=settings.OLLAMA_BASE_URL,
                llm_model=settings.OLLAMA_LLM_MODEL,
                embedding_model=settings.OLLAMA_EMBEDDING_MODEL,
            )
            logger.info("✅ RagAgent initialized")
        return self._agent
    
    def _build_source_info(self, result: SearchResult, base_url: str) -> SourceInfo:
        """Построить SourceInfo из SearchResult."""
        meta = result.metadata
        file_path = meta.file_path
        file_name = file_path.split("/")[-1] if file_path else "unknown"
        
        encoded_path = quote(file_path, safe="")
        download_url = f"{base_url}/api/files/download?path={encoded_path}"
        
        return SourceInfo(
            file_path=file_path,
            file_name=file_name,
            chunk_index=meta.chunk_index,
            similarity=result.final_score,
            download_url=download_url,
            title=meta.title,
            summary=meta.summary,
            category=meta.category,
            modified_at=meta.modified_at,
        )
    
    def stream(
        self,
        query: str,
        conversation_id: str | None = None,
        base_url: str = ""
    ) -> Iterator[StreamEvent]:
        """
        Потоковая генерация ответа.
        
        Events:
        1. tool_call — промежуточные сообщения о поиске
        2. metadata — sources после поиска
        3. chunk — части текстового ответа
        4. done — завершение
        """
        logger.info(f"📨 Complex Agent stream: {query[:50]}...")
        
        # Собираем промежуточные сообщения
        intermediate_messages: List[str] = []
        
        def stream_callback(message: str):
            """Callback для промежуточных сообщений."""
            intermediate_messages.append(message)
            # Сразу отправляем как tool_call event
            # (будет обработано в цикле ниже)
        
        try:
            agent = self._get_agent()
            
            # Извлекаем фильтры и ищем
            stream_callback("🔎 Анализирую запрос...")
            
            filters = agent._extract_filters(query)
            
            # Embedding
            embedding = agent.vector_store.get_embedding(
                query, agent.ollama_url, agent.embedding_model
            )
            
            if not embedding:
                yield StreamEvent(type="error", data={"error": "Не удалось обработать запрос"})
                return
            
            # Robust search с callback'ами
            from .robust_search import robust_search
            
            results, debug_info = robust_search(
                vector_store=agent.vector_store,
                embedding=embedding,
                filters=filters.to_search_filter(),
                limit=10,
                stream_callback=stream_callback
            )
            
            # Отправляем промежуточные сообщения
            for msg in intermediate_messages:
                yield StreamEvent(
                    type="tool_call",
                    data={"name": "search_status", "message": msg}
                )
            
            # Sources
            if results:
                sources = [self._build_source_info(r, base_url) for r in results]
                yield StreamEvent(
                    type="metadata",
                    data={
                        "conversation_id": conversation_id or "",
                        "sources": [s.to_dict() for s in sources],
                    }
                )
                logger.info(f"📎 Sent {len(sources)} sources")
            
            # Генерируем ответ
            if not results:
                yield StreamEvent(
                    type="chunk",
                    data={"content": "К сожалению, по вашему запросу документы не найдены."}
                )
            else:
                # Streaming generate
                for chunk in agent._stream_generate(query, results):
                    yield StreamEvent(type="chunk", data={"content": chunk})
            
            yield StreamEvent(type="done", data={})
            
        except Exception as e:
            logger.error(f"❌ Complex Agent error: {e}")
            yield StreamEvent(type="error", data={"error": str(e)})
