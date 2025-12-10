"""
Complex Agent Backend — Agentic RAG с robust search и реранкингом.

Компоненты:
- VectorStoreAdapter: semantic + structured поиск через Supabase
- robust_search: итеративный поиск с ослаблением фильтров
- reranker: комбинированный реранкинг (дата + категория + similarity)
- RagAgent: LangChain агент с streaming callbacks
"""
from .backend import ComplexAgentBackend

__all__ = ["ComplexAgentBackend"]
