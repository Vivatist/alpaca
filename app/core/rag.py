"""
RAG (Retrieval-Augmented Generation) - векторный поиск + генерация ответа
"""

from typing import List, Dict, Optional
import httpx
import logging

from settings import settings
from app.core.embedder import Embedder

logger = logging.getLogger(__name__)


class RAGSystem:
    """Система RAG для поиска и генерации ответов"""
    
    def __init__(
        self,
        ollama_url: str = None,
        llm_model: str = None,
        embed_model: str = None,
        top_k: int = None,
        similarity_threshold: float = None
    ):
        self.ollama_url = ollama_url or settings.OLLAMA_BASE_URL
        self.llm_model = llm_model or settings.OLLAMA_LLM_MODEL
        self.embed_model = embed_model or settings.OLLAMA_EMBED_MODEL
        self.top_k = top_k or settings.TOP_K_RESULTS
        self.similarity_threshold = similarity_threshold or settings.SIMILARITY_THRESHOLD
        
        self.embedder = Embedder(
            ollama_url=self.ollama_url,
            model=self.embed_model
        )
    
    async def search_similar(
        self,
        query: str,
        db_connection  # asyncpg connection
    ) -> List[Dict]:
        """
        Векторный поиск похожих документов
        
        Args:
            query: Поисковый запрос
            db_connection: Подключение к БД
        
        Returns:
            Список найденных документов с метаданными
        """
        logger.info(f"Searching for: {query}")
        
        # Генерируем embedding для запроса
        query_embedding = await self.embedder.generate_embedding(query)
        
        if not query_embedding:
            logger.error("Failed to generate query embedding")
            return []
        
        # Векторный поиск в БД через pgvector
        # Используем cosine distance: 1 - (embedding <=> query_embedding)
        sql = """
            SELECT 
                id,
                file_hash,
                file_path,
                chunk_index,
                chunk_text,
                1 - (embedding <=> $1::vector) AS similarity,
                metadata
            FROM documents
            WHERE embedding IS NOT NULL
              AND 1 - (embedding <=> $1::vector) > $2
            ORDER BY embedding <=> $1::vector
            LIMIT $3
        """
        
        try:
            results = await db_connection.fetch(
                sql,
                query_embedding,
                self.similarity_threshold,
                self.top_k
            )
            
            documents = []
            for row in results:
                documents.append({
                    'id': row['id'],
                    'file_hash': row['file_hash'],
                    'file_path': row['file_path'],
                    'chunk_index': row['chunk_index'],
                    'chunk_text': row['chunk_text'],
                    'similarity': float(row['similarity']),
                    'metadata': row['metadata']
                })
            
            logger.info(f"Found {len(documents)} similar documents")
            return documents
        
        except Exception as e:
            logger.error(f"Error searching documents: {e}", exc_info=True)
            return []
    
    async def generate_answer(
        self,
        query: str,
        context_documents: List[Dict]
    ) -> Optional[str]:
        """
        Генерирует ответ на основе найденных документов
        
        Args:
            query: Вопрос пользователя
            context_documents: Найденные релевантные документы
        
        Returns:
            Сгенерированный ответ или None при ошибке
        """
        if not context_documents:
            logger.warning("No context documents provided")
            return None
        
        # Формируем контекст из найденных документов
        context_parts = []
        for idx, doc in enumerate(context_documents, 1):
            source = doc.get('file_path', 'Unknown')
            text = doc.get('chunk_text', '')
            similarity = doc.get('similarity', 0)
            
            context_parts.append(
                f"[Источник {idx}: {source} (релевантность: {similarity:.2f})]\n{text}"
            )
        
        context = "\n\n---\n\n".join(context_parts)
        
        # Формируем промпт для LLM
        prompt = f"""На основе предоставленного контекста ответь на вопрос пользователя.
Используй только информацию из контекста. Если в контексте нет ответа, скажи об этом.

КОНТЕКСТ:
{context}

ВОПРОС: {query}

ОТВЕТ:"""
        
        logger.info(f"Generating answer with {len(context_documents)} context documents")
        logger.debug(f"Prompt length: {len(prompt)} chars")
        
        try:
            async with httpx.AsyncClient(timeout=settings.OLLAMA_TIMEOUT) as client:
                response = await client.post(
                    f"{self.ollama_url}/api/generate",
                    json={
                        "model": self.llm_model,
                        "prompt": prompt,
                        "stream": False,
                        "options": {
                            "temperature": 0.7,
                            "top_p": 0.9,
                        }
                    }
                )
                
                if response.status_code != 200:
                    logger.error(
                        f"Ollama generation error: {response.status_code} - {response.text}"
                    )
                    return None
                
                result = response.json()
                answer = result.get('response', '').strip()
                
                logger.info(f"Generated answer: {len(answer)} chars")
                return answer
        
        except httpx.TimeoutException:
            logger.error("Timeout while generating answer")
            return None
        except Exception as e:
            logger.error(f"Error generating answer: {e}", exc_info=True)
            return None
    
    async def query(
        self,
        question: str,
        db_connection
    ) -> Dict:
        """
        Полный цикл RAG: поиск + генерация ответа
        
        Args:
            question: Вопрос пользователя
            db_connection: Подключение к БД
        
        Returns:
            Словарь с ответом и метаданными
        """
        # 1. Векторный поиск
        documents = await self.search_similar(question, db_connection)
        
        if not documents:
            return {
                'success': False,
                'question': question,
                'answer': None,
                'sources': [],
                'error': 'No relevant documents found'
            }
        
        # 2. Генерация ответа
        answer = await self.generate_answer(question, documents)
        
        if not answer:
            return {
                'success': False,
                'question': question,
                'answer': None,
                'sources': documents,
                'error': 'Failed to generate answer'
            }
        
        # 3. Формируем результат
        sources = [
            {
                'file_path': doc['file_path'],
                'chunk_index': doc['chunk_index'],
                'similarity': doc['similarity'],
                'text_preview': doc['chunk_text'][:200] + '...'
            }
            for doc in documents
        ]
        
        return {
            'success': True,
            'question': question,
            'answer': answer,
            'sources': sources,
            'num_sources': len(documents)
        }


async def ask_question(question: str, db_connection) -> Dict:
    """
    Удобная функция для RAG запросов
    
    Args:
        question: Вопрос
        db_connection: Подключение к БД
    
    Returns:
        Ответ с источниками
    """
    rag = RAGSystem()
    return await rag.query(question, db_connection)
