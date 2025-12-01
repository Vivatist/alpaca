"""
Тесты для модуля эмбеддинга (custom_embedder)
"""
import pytest
import responses
from unittest.mock import Mock, patch, MagicMock
from core.application.document_processing.embedders import custom_embedding
from settings import settings
from core.domain.files.models import FileSnapshot


class TestEmbedding:
    """Тесты функции embedding"""
    
    @responses.activate
    def test_embedding_success(self, test_db):
        """Тест успешного создания эмбеддингов"""
        # Mock Ollama API
        responses.add(
            responses.POST,
            f"{settings.OLLAMA_BASE_URL}/api/embeddings",
            json={'embedding': [0.1] * 1024},
            status=200
        )
        
        chunks = ["Тестовый чанк 1", "Тестовый чанк 2"]
        file_hash = "test_hash_embed_123"
        file_path = "/tmp/test_embed.txt"
        
        file = FileSnapshot(hash=file_hash, path=file_path, status_sync="added")
        result = custom_embedding(test_db, file, chunks)
        
        assert result == 2
        assert len(responses.calls) == 2
    
    def test_embedding_empty_chunks(self, test_db):
        """Тест эмбеддинга с пустым списком чанков"""
        chunks = []
        file_hash = "test_hash_empty"
        file_path = "/tmp/test_empty.txt"
        
        file = FileSnapshot(hash=file_hash, path=file_path, status_sync="added")
        result = custom_embedding(test_db, file, chunks)
        
        assert result == 0
    
    @responses.activate
    def test_embedding_ollama_error(self, test_db):
        """Тест обработки ошибки от Ollama"""
        # Mock Ollama API с ошибкой
        responses.add(
            responses.POST,
            f"{settings.OLLAMA_BASE_URL}/api/embeddings",
            json={'error': 'Service unavailable'},
            status=503
        )
        
        chunks = ["Тестовый чанк"]
        file_hash = "test_hash_error"
        file_path = "/tmp/test_error.txt"
        
        file = FileSnapshot(hash=file_hash, path=file_path, status_sync="added")
        result = custom_embedding(test_db, file, chunks)
        
        assert result == 0
    
    @responses.activate
    def test_embedding_partial_success(self, test_db):
        """Тест частичного успеха (одни чанки успешны, другие нет)"""
        # Mock Ollama API - первый успешен, второй с ошибкой
        responses.add(
            responses.POST,
            f"{settings.OLLAMA_BASE_URL}/api/embeddings",
            json={'embedding': [0.1] * 1024},
            status=200
        )
        responses.add(
            responses.POST,
            f"{settings.OLLAMA_BASE_URL}/api/embeddings",
            json={'error': 'Error'},
            status=500
        )
        responses.add(
            responses.POST,
            f"{settings.OLLAMA_BASE_URL}/api/embeddings",
            json={'embedding': [0.1] * 1024},
            status=200
        )
        
        chunks = ["Чанк 1", "Чанк 2", "Чанк 3"]
        file_hash = "test_hash_partial"
        file_path = "/tmp/test_partial.txt"
        
        file = FileSnapshot(hash=file_hash, path=file_path, status_sync="added")
        result = custom_embedding(test_db, file, chunks)
        
        # Должны быть сохранены 2 из 3 чанков
        assert result == 2
    
    @responses.activate
    def test_embedding_no_embedding_in_response(self, test_db):
        """Тест когда Ollama возвращает ответ без embedding"""
        responses.add(
            responses.POST,
            f"{settings.OLLAMA_BASE_URL}/api/embeddings",
            json={'model': 'bge-m3'},  # Нет поля 'embedding'
            status=200
        )
        
        chunks = ["Тестовый чанк"]
        file_hash = "test_hash_no_embed"
        file_path = "/tmp/test_no_embed.txt"
        
        file = FileSnapshot(hash=file_hash, path=file_path, status_sync="added")
        result = custom_embedding(test_db, file, chunks)
        
        assert result == 0
    
    @responses.activate
    def test_embedding_database_commit(self, test_db):
        """Тест что эмбеддинги сохраняются в БД"""
        responses.add(
            responses.POST,
            f"{settings.OLLAMA_BASE_URL}/api/embeddings",
            json={'embedding': [0.1] * 1024},
            status=200
        )
        
        chunks = ["Тестовый чанк для сохранения"]
        file_hash = "test_hash_db_123"
        file_path = "/tmp/test_db.txt"
        
        file = FileSnapshot(hash=file_hash, path=file_path, status_sync="added")
        result = custom_embedding(test_db, file, chunks)
        
        assert result == 1
        
        # Проверяем что чанк действительно сохранён в БД
        with test_db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COUNT(*) FROM chunks WHERE metadata->>'file_hash' = %s",
                    (file_hash,)
                )
                count = cur.fetchone()[0]
                assert count == 1
