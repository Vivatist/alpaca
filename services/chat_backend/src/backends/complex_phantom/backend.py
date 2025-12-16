"""
ComplexPhantomBackend — копия complex_agent для экспериментов.

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

logger = get_logger("chat_backend.complex_phantom")


class ComplexPhantomBackend(ChatBackend):
    """
    Complex Phantom Backend — копия complex_agent для экспериментов.
    
    Agentic RAG с robust search и реранкингом.
    """
    
    def __init__(self):
        self._agent: RagAgent | None = None
        self._vector_store: VectorStoreAdapter | None = None
    
    @property
    def name(self) -> str:
        return "complex_phantom"
    
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
    
    def _build_source_from_chunk(self, chunk: dict, base_url: str) -> SourceInfo:
        """Построить SourceInfo из chunk dict (формат MCP)."""
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
    
    def _check_langchain(self) -> bool:
        """Проверить доступность LangChain."""
        try:
            from langchain_ollama import ChatOllama
            from langgraph.prebuilt import create_react_agent
            return True
        except ImportError:
            logger.warning("LangChain not available")
            return False
    
    def _create_search_func(self):
        """Создать функцию поиска через vector_store."""
        vector_store = self._get_vector_store()
        
        def search_func(query: str, top_k: int = 5):
            """Поиск документов по запросу."""
            # Получаем embedding
            embedding = vector_store.get_embedding(
                query, settings.OLLAMA_BASE_URL, settings.OLLAMA_EMBEDDING_MODEL
            )
            if not embedding:
                return []
            
            # Поиск через search_semantic
            results = vector_store.search_semantic(embedding, limit=top_k)
            
            # Конвертируем SearchHit в формат chunks для LangChain
            chunks = []
            for hit in results:
                # MetadataModel — pydantic, используем model_dump()
                meta_dict = hit.metadata.model_dump() if hasattr(hit.metadata, 'model_dump') else {}
                chunks.append({
                    "content": hit.content,
                    "metadata": meta_dict,
                    "similarity": hit.base_score,
                })
            return chunks
        
        return search_func
    
    def stream(
        self,
        query: str,
        conversation_id: str | None = None,
        base_url: str = ""
    ) -> Iterator[StreamEvent]:
        """
        Потоковая генерация ответа через LangChain Agent.
        
        Использует подход из agent backend:
        - Агент сам решает нужен ли поиск
        - На простые вопросы (2+2) отвечает напрямую
        - На вопросы про документы — использует search_documents tool
        """
        logger.info(f"📨 Complex Phantom stream: {query[:50]}...")
        
        # Проверяем LangChain
        if not self._check_langchain():
            yield StreamEvent(type="error", data={"error": "LangChain не установлен"})
            return
        
        try:
            from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, ToolMessage
            from .langchain_agent import create_agent, SearchContext, DEFAULT_SYSTEM_PROMPT
            
            # Контекст для сбора найденных документов
            search_context = SearchContext()
            
            # Создаём агента
            agent = create_agent(
                base_url=settings.OLLAMA_BASE_URL,
                model=settings.OLLAMA_LLM_MODEL,
                search_func=self._create_search_func(),
                context=search_context
            )
            
            messages = [
                SystemMessage(content=DEFAULT_SYSTEM_PROMPT),
                HumanMessage(content=query)
            ]
            
            sources_sent = False
            
            # Стримим ответ агента
            for event in agent.stream({"messages": messages}, stream_mode="messages"):
                if isinstance(event, tuple) and len(event) >= 1:
                    message = event[0]
                    
                    # После tool вызова отправляем sources
                    if isinstance(message, ToolMessage):
                        if search_context.chunks and not sources_sent:
                            sources = [self._build_source_from_chunk(c, base_url) for c in search_context.chunks]
                            yield StreamEvent(
                                type="metadata",
                                data={
                                    "conversation_id": conversation_id or "",
                                    "sources": [s.to_dict() for s in sources],
                                }
                            )
                            sources_sent = True
                            logger.info(f"📎 Sent {len(sources)} sources")
                        continue
                    
                    if isinstance(message, AIMessage):
                        # Tool calls
                        if hasattr(message, 'tool_calls') and message.tool_calls:
                            for tc in message.tool_calls:
                                yield StreamEvent(
                                    type="tool_call",
                                    data={"name": tc.get("name", ""), "args": tc.get("args", {})}
                                )
                        # Text content
                        elif message.content:
                            yield StreamEvent(type="chunk", data={"content": message.content})
            
            # Если sources не были отправлены — пустой список
            if not sources_sent:
                yield StreamEvent(
                    type="metadata",
                    data={"conversation_id": conversation_id or "", "sources": []}
                )
            
            yield StreamEvent(type="done", data={})
            
        except Exception as e:
            logger.error(f"❌ Complex Phantom error: {e}")
            yield StreamEvent(type="error", data={"error": str(e)})
