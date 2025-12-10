"""
RAG Agent — LangChain агент с извлечением фильтров и streaming.

RagAgent:
1. Извлекает метаданные из запроса (category, company, person, etc.)
2. Вызывает search_documents через robust_search
3. Отправляет промежуточные сообщения через stream_callback
4. Генерирует финальный ответ на основе найденных документов
"""
import json
import re
from typing import List, Optional, Callable, Iterator

from logging_config import get_logger
from .schemas import (
    SearchResult, ExtractedFilters, AgentAnswer, 
    RetryDebugInfo, SearchFilter
)
from .vector_store import VectorStoreAdapter
from .search_tool import create_search_tool, SearchContext
from .robust_search import robust_search, StreamCallback
from .config import (
    DOCUMENT_CATEGORIES, 
    AGENT_SYSTEM_PROMPT,
    QUERY_EXTRACTION_PROMPT,
    DEFAULT_SEARCH_LIMIT,
)

logger = get_logger("chat_backend.complex_agent.agent")


class RagAgent:
    """
    RAG агент с LangChain, robust search и streaming.
    
    Может работать в двух режимах:
    1. С LangChain агентом (если установлен langchain)
    2. Без агента — прямой вызов search + generate
    """
    
    def __init__(
        self,
        vector_store: VectorStoreAdapter,
        ollama_url: str,
        llm_model: str,
        embedding_model: str,
        system_prompt: Optional[str] = None
    ):
        self.vector_store = vector_store
        self.ollama_url = ollama_url
        self.llm_model = llm_model
        self.embedding_model = embedding_model
        self.system_prompt = system_prompt or AGENT_SYSTEM_PROMPT
        
        # Проверяем доступность LangChain
        self._langchain_available = self._check_langchain()
    
    def _check_langchain(self) -> bool:
        """Проверить доступность LangChain."""
        try:
            from langchain_core.messages import HumanMessage
            from langchain_ollama import ChatOllama
            return True
        except ImportError:
            logger.warning("LangChain not available, using direct mode")
            return False
    
    def answer(
        self,
        user_query: str,
        stream_callback: Optional[StreamCallback] = None
    ) -> AgentAnswer:
        """
        Синхронный ответ на запрос пользователя.
        
        Args:
            user_query: Запрос пользователя
            stream_callback: Callback для промежуточных сообщений
            
        Returns:
            AgentAnswer с финальным текстом и использованными документами
        """
        # 1. Извлекаем фильтры из запроса
        if stream_callback:
            stream_callback("🔎 Анализирую запрос...")
        
        filters = self._extract_filters(user_query)
        
        # 2. Получаем embedding запроса
        embedding = self.vector_store.get_embedding(
            user_query, self.ollama_url, self.embedding_model
        )
        
        if not embedding:
            return AgentAnswer(
                final_text="Ошибка: не удалось обработать запрос",
                used_documents=[],
                debug_info=RetryDebugInfo()
            )
        
        # 3. Выполняем robust search
        results, debug_info = robust_search(
            vector_store=self.vector_store,
            embedding=embedding,
            filters=filters.to_search_filter(),
            limit=DEFAULT_SEARCH_LIMIT,
            stream_callback=stream_callback
        )
        
        # 4. Генерируем ответ
        if stream_callback:
            stream_callback("💭 Формирую ответ...")
        
        final_text = self._generate_answer(user_query, results)
        
        return AgentAnswer(
            final_text=final_text,
            used_documents=results,
            debug_info=debug_info
        )
    
    def stream_answer(
        self,
        user_query: str,
        stream_callback: Optional[StreamCallback] = None
    ) -> Iterator[str]:
        """
        Потоковый ответ на запрос.
        
        Yields:
            Части текстового ответа
        """
        # 1. Извлекаем фильтры
        if stream_callback:
            stream_callback("🔎 Анализирую запрос...")
        
        filters = self._extract_filters(user_query)
        
        # 2. Обогащаем query для semantic search
        # Entity и keywords добавляются в query для embedding (не SQL!)
        enriched_query = self._enrich_query(user_query, filters)
        
        # 3. Embedding обогащённого запроса
        embedding = self.vector_store.get_embedding(
            enriched_query, self.ollama_url, self.embedding_model
        )
        
        if not embedding:
            yield "Ошибка: не удалось обработать запрос"
            return
        
        # 4. Search (SQL фильтры: только category и date)
        results, debug_info = robust_search(
            vector_store=self.vector_store,
            embedding=embedding,
            filters=filters.to_search_filter(),
            limit=DEFAULT_SEARCH_LIMIT,
            stream_callback=stream_callback
        )
        
        if not results:
            yield "К сожалению, по вашему запросу документы не найдены."
            return
        
        # 5. Stream generate
        if stream_callback:
            stream_callback("💭 Формирую ответ...")
        
        yield from self._stream_generate(user_query, results)
    
    def _enrich_query(self, query: str, filters: ExtractedFilters) -> str:
        """
        Обогатить query для semantic search.
        
        Entity и keywords добавляются к запросу для embedding.
        Это позволяет семантически найти "Акпан", "АкпанОМ", "АКПАН".
        
        Args:
            query: Исходный запрос пользователя
            filters: Извлечённые фильтры
            
        Returns:
            Обогащённый запрос
        """
        parts = [query]
        
        if filters.entity:
            parts.append(filters.entity)
        
        if filters.keywords:
            parts.extend(filters.keywords[:3])  # Макс 3 keywords
        
        enriched = " ".join(parts)
        logger.debug(f"Enriched query: {enriched}")
        return enriched

    def _extract_filters(self, query: str) -> ExtractedFilters:
        """
        Извлечь фильтры из запроса через LLM.
        
        Args:
            query: Запрос пользователя
            
        Returns:
            ExtractedFilters с category, entity, keywords, etc.
        """
        import requests
        
        categories_list = "\n".join(f"- {cat}" for cat in DOCUMENT_CATEGORIES)
        prompt = QUERY_EXTRACTION_PROMPT.format(
            categories=categories_list,
            query=query
        )
        
        try:
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": self.llm_model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.1, "num_predict": 300}
                },
                timeout=60
            )
            
            if response.status_code != 200:
                logger.warning(f"Filter extraction failed: {response.status_code}")
                return ExtractedFilters()
            
            llm_response = response.json().get("response", "")
            return self._parse_extracted_filters(llm_response)
            
        except Exception as e:
            logger.error(f"Filter extraction error: {e}")
            return ExtractedFilters()
    
    def _parse_extracted_filters(self, response: str) -> ExtractedFilters:
        """Парсинг JSON из ответа LLM."""
        try:
            # Ищем JSON в ответе
            json_match = re.search(r'\{[\s\S]*\}', response)
            if not json_match:
                return ExtractedFilters()
            
            data = json.loads(json_match.group())
            
            # Валидация категории
            category = data.get("category")
            if category and category not in DOCUMENT_CATEGORIES:
                category = None
            
            return ExtractedFilters(
                category=category,
                entity=data.get("entity"),  # Единое поле для company/person
                keywords=data.get("keywords"),
                date_from=data.get("date_from"),
                date_to=data.get("date_to"),
            )
            
        except (json.JSONDecodeError, TypeError) as e:
            logger.debug(f"Filter parse error: {e}")
            return ExtractedFilters()
    
    def _generate_answer(self, query: str, results: List[SearchResult]) -> str:
        """
        Сгенерировать финальный ответ на основе найденных документов.
        """
        import requests
        
        if not results:
            return "К сожалению, по вашему запросу документы не найдены."
        
        # Формируем контекст из документов
        context = self._build_context(results)
        
        prompt = f"""{self.system_prompt}

Контекст из найденных документов:
{context}

Вопрос пользователя: {query}

Ответ (кратко, по делу, на основе документов):"""
        
        try:
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": self.llm_model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.3, "num_predict": 1000}
                },
                timeout=120
            )
            
            if response.status_code == 200:
                return response.json().get("response", "").strip()
            else:
                logger.error(f"Generate failed: {response.status_code}")
                return "Ошибка при генерации ответа"
                
        except Exception as e:
            logger.error(f"Generate error: {e}")
            return "Ошибка при генерации ответа"
    
    def _stream_generate(
        self, 
        query: str, 
        results: List[SearchResult]
    ) -> Iterator[str]:
        """
        Потоковая генерация ответа.
        """
        import requests
        
        context = self._build_context(results)
        
        prompt = f"""{self.system_prompt}

Контекст из найденных документов:
{context}

Вопрос пользователя: {query}

Ответ (кратко, по делу, на основе документов):"""
        
        try:
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": self.llm_model,
                    "prompt": prompt,
                    "stream": True,
                    "options": {"temperature": 0.3, "num_predict": 1000}
                },
                stream=True,
                timeout=120
            )
            
            if response.status_code != 200:
                yield "Ошибка при генерации ответа"
                return
            
            for line in response.iter_lines():
                if line:
                    try:
                        data = json.loads(line)
                        if "response" in data:
                            yield data["response"]
                        if data.get("done"):
                            break
                    except json.JSONDecodeError:
                        continue
                        
        except Exception as e:
            logger.error(f"Stream generate error: {e}")
            yield "Ошибка при генерации ответа"
    
    def _build_context(self, results: List[SearchResult]) -> str:
        """
        Построить контекст из найденных документов для LLM.
        """
        parts = []
        
        for i, result in enumerate(results[:5], 1):  # Максимум 5 документов
            meta = result.metadata
            title = meta.title or meta.file_path.split("/")[-1]
            
            part = f"[Документ {i}: {title}]"
            if meta.category:
                part += f" (категория: {meta.category})"
            if meta.modified_at:
                part += f" (дата: {meta.modified_at[:10]})"
            part += f"\n{result.content}"
            
            parts.append(part)
        
        return "\n\n---\n\n".join(parts)
