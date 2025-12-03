"""
Тесты для эмбеддеров.
"""
import pytest
from unittest.mock import MagicMock, patch
from contracts import FileSnapshot
from embedders import EMBEDDERS, build_embedder


class TestEmbedderRegistry:
    """Тесты реестра эмбеддеров."""
    
    def test_registry_has_ollama(self):
        """Реестр содержит ollama embedder."""
        assert "ollama" in EMBEDDERS
    
    def test_build_embedder_returns_callable(self):
        """build_embedder возвращает callable."""
        embedder = build_embedder()
        assert callable(embedder)


class TestOllamaEmbedder:
    """Тесты ollama_embedder (с моками)."""
    
    def test_empty_chunks_returns_zero(self):
        """Пустой список чанков возвращает 0."""
        from embedders.ollama import ollama_embedder
        
        repo = MagicMock()
        file = FileSnapshot(hash="test", path="/test.txt", raw_text="")
        
        result = ollama_embedder(repo, file, [], {})
        
        assert result == 0
        repo.save_chunk.assert_not_called()
    
    @patch('embedders.ollama._get_embeddings_batch')
    def test_successful_embedding(self, mock_get_embeddings):
        """Успешный эмбеддинг сохраняет чанки."""
        from embedders.ollama import ollama_embedder
        
        # Мокаем эмбеддинги
        mock_get_embeddings.return_value = [[0.1] * 1024, [0.2] * 1024]
        
        repo = MagicMock()
        repo.delete_chunks_by_hash.return_value = 0
        
        file = FileSnapshot(hash="test123", path="/test.txt", raw_text="")
        chunks = ["Chunk 1", "Chunk 2"]
        
        result = ollama_embedder(repo, file, chunks, {"extension": "txt"})
        
        assert result == 2
        assert repo.save_chunk.call_count == 2
        repo.delete_chunks_by_hash.assert_called_once_with("test123")
    
    @patch('embedders.ollama._get_embeddings_batch')
    def test_embedding_failure_returns_zero(self, mock_get_embeddings):
        """При ошибке эмбеддинга возвращает 0."""
        from embedders.ollama import ollama_embedder
        
        mock_get_embeddings.return_value = []  # Ошибка
        
        repo = MagicMock()
        repo.delete_chunks_by_hash.return_value = 0
        
        file = FileSnapshot(hash="test", path="/test.txt", raw_text="")
        chunks = ["Chunk 1"]
        
        result = ollama_embedder(repo, file, chunks, {})
        
        assert result == 0
