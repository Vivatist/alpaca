"""
MCP Client для Agent Backend.

Поиск документов через MCP-сервер.
"""
from typing import List, Dict, Any

import httpx

from logging_config import get_logger

logger = get_logger("chat_backend.agent.mcp")


def search_via_mcp(
    query: str,
    mcp_url: str,
    top_k: int = 5,
    timeout: float = 30.0
) -> List[Dict[str, Any]]:
    """
    Поиск документов через MCP-сервер.
    
    Args:
        query: Поисковый запрос
        mcp_url: URL MCP-сервера
        top_k: Количество результатов
        timeout: Таймаут запроса
        
    Returns:
        Список чанков с content, metadata, similarity
    """
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.post(
                f"{mcp_url}/tools/search_documents",
                json={"query": query, "top_k": top_k}
            )
            response.raise_for_status()
            data = response.json()
            
            chunks = []
            for c in data.get("chunks", []):
                chunks.append({
                    "content": c.get("content", ""),
                    "metadata": {
                        "file_path": c.get("file_path", ""),
                        "file_name": c.get("file_name", ""),
                        "title": c.get("title"),
                        "summary": c.get("summary"),
                        "category": c.get("category"),
                        "chunk_index": c.get("chunk_index", 0),
                    },
                    "similarity": c.get("similarity", 0),
                })
            
            logger.debug(f"MCP search '{query[:30]}...' → {len(chunks)} chunks")
            return chunks
            
    except Exception as e:
        logger.error(f"MCP search error: {e}")
        return []
