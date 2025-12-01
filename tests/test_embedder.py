"""
Тесты для модуля эмбеддинга (custom_embedder, langchain_embedder)
"""
import pytest
import responses
from unittest.mock import Mock, patch, MagicMock
from core.application.document_processing.embedders import custom_embedding
from core.application.document_processing.embedders.langchain_embedder import langchain_embedding
from settings import settings
from core.domain.files.models import FileSnapshot


class TestEmbedding:
    """Тесты функции embedding (batch API)"""
    
    @responses.activate
    def test_embedding_success(self, test_db):
        """Тест успешного создания эмбеддингов через batch API"""
        # Mock Ollama batch API
        responses.add(
            responses.POST,
            f"{settings.OLLAMA_BASE_URL}/api/embed",
            json={'embeddings': [[0.1] * 1024, [0.2] * 1024]},
            status=200
        )
        
        chunks = ["Тестовый чанк 1", "Тестовый чанк 2"]
        file_hash = "test_hash_embed_123"
        file_path = "/tmp/test_embed.txt"
        
        file = FileSnapshot(hash=file_hash, path=file_path, status_sync="added")
        result = custom_embedding(test_db, file, chunks)
        
        assert result == 2
        assert len(responses.calls) == 1  # Один batch-запрос вместо двух
    
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
            f"{settings.OLLAMA_BASE_URL}/api/embed",
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
    def test_embedding_batch_partial_failure(self, test_db):
        """Тест когда один батч успешен, а другой нет"""
        # Первый батч успешен
        responses.add(
            responses.POST,
            f"{settings.OLLAMA_BASE_URL}/api/embed",
            json={'embeddings': [[0.1] * 1024, [0.2] * 1024]},
            status=200
        )
        # Второй батч — ошибка
        responses.add(
            responses.POST,
            f"{settings.OLLAMA_BASE_URL}/api/embed",
            json={'error': 'Error'},
            status=500
        )
        
        # Создаём чанки для двух батчей (BATCH_SIZE=50, но для теста патчим)
        from core.application.document_processing.embedders import custom_embedder
        original_batch_size = custom_embedder.BATCH_SIZE
        custom_embedder.BATCH_SIZE = 2  # Временно уменьшаем для теста
        
        try:
            chunks = ["Чанк 1", "Чанк 2", "Чанк 3", "Чанк 4"]
            file_hash = "test_hash_partial_batch"
            file_path = "/tmp/test_partial_batch.txt"
            
            file = FileSnapshot(hash=file_hash, path=file_path, status_sync="added")
            result = custom_embedding(test_db, file, chunks)
            
            # Должны быть сохранены 2 из 4 чанков (первый батч)
            assert result == 2
        finally:
            custom_embedder.BATCH_SIZE = original_batch_size
    
    @responses.activate
    def test_embedding_no_embeddings_in_response(self, test_db):
        """Тест когда Ollama возвращает ответ без embeddings"""
        responses.add(
            responses.POST,
            f"{settings.OLLAMA_BASE_URL}/api/embed",
            json={'model': 'bge-m3'},  # Нет поля 'embeddings'
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
            f"{settings.OLLAMA_BASE_URL}/api/embed",
            json={'embeddings': [[0.1] * 1024]},
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

    @responses.activate
    def test_embedding_deletes_old_chunks(self, test_db):
        """Тест что старые чанки удаляются перед вставкой новых"""
        file_hash = "test_hash_delete_old"
        file_path = "/tmp/test_delete_old.txt"
        
        # Mock Ollama batch API - первая вставка
        responses.add(
            responses.POST,
            f"{settings.OLLAMA_BASE_URL}/api/embed",
            json={'embeddings': [[0.1] * 1024, [0.1] * 1024, [0.1] * 1024]},
            status=200
        )
        
        # Первая вставка - 3 чанка
        file = FileSnapshot(hash=file_hash, path=file_path, status_sync="added")
        chunks_v1 = ["Чанк 1 v1", "Чанк 2 v1", "Чанк 3 v1"]
        result1 = custom_embedding(test_db, file, chunks_v1)
        assert result1 == 3
        
        # Проверяем что 3 чанка в БД
        with test_db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COUNT(*) FROM chunks WHERE metadata->>'file_hash' = %s",
                    (file_hash,)
                )
                assert cur.fetchone()[0] == 3
        
        # Mock для второй вставки
        responses.add(
            responses.POST,
            f"{settings.OLLAMA_BASE_URL}/api/embed",
            json={'embeddings': [[0.2] * 1024, [0.2] * 1024]},
            status=200
        )
        
        # Вторая вставка - 2 чанка (должны удалиться старые 3)
        chunks_v2 = ["Чанк 1 v2", "Чанк 2 v2"]
        result2 = custom_embedding(test_db, file, chunks_v2)
        assert result2 == 2
        
        # Проверяем что теперь только 2 чанка (старые удалены)
        with test_db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COUNT(*) FROM chunks WHERE metadata->>'file_hash' = %s",
                    (file_hash,)
                )
                assert cur.fetchone()[0] == 2
                
                # Проверяем что это новые чанки
                cur.execute(
                    "SELECT content FROM chunks WHERE metadata->>'file_hash' = %s ORDER BY metadata->>'chunk_index'",
                    (file_hash,)
                )
                contents = [row[0] for row in cur.fetchall()]
                assert contents == ["Чанк 1 v2", "Чанк 2 v2"]


class TestLangChainEmbedding:
    """Тесты для langchain_embedding"""
    
    def test_langchain_empty_chunks(self, test_db):
        """Тест с пустым списком чанков"""
        file = FileSnapshot(hash="test_lc_empty", path="/tmp/test_lc_empty.txt", status_sync="added")
        result = langchain_embedding(test_db, file, [])
        assert result == 0
    
    def test_langchain_no_provider(self, test_db):
        """Тест когда провайдер недоступен"""
        file = FileSnapshot(hash="test_lc_no_provider", path="/tmp/test_lc_no_prov.txt", status_sync="added")
        
        # Патчим _build_default_provider чтобы вернул None
        with patch('core.application.document_processing.embedders.langchain_embedder._build_default_provider', return_value=None):
            result = langchain_embedding(test_db, file, ["Чанк"])
            assert result == 0
    
    def test_langchain_success(self, test_db):
        """Тест успешного эмбеддинга через LangChain"""
        file_hash = "test_lc_success"
        file_path = "/tmp/test_lc_success.txt"
        file = FileSnapshot(hash=file_hash, path=file_path, status_sync="added")
        chunks = ["Чанк 1", "Чанк 2"]
        
        # Mock провайдер
        mock_provider = Mock()
        mock_provider.embed_documents.return_value = [[0.1] * 1024, [0.2] * 1024]
        
        result = langchain_embedding(test_db, file, chunks, provider=mock_provider)
        
        assert result == 2
        mock_provider.embed_documents.assert_called_once_with(chunks)
        
        # Проверяем что чанки в БД
        with test_db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COUNT(*) FROM chunks WHERE metadata->>'file_hash' = %s",
                    (file_hash,)
                )
                assert cur.fetchone()[0] == 2
    
    def test_langchain_provider_error(self, test_db):
        """Тест ошибки провайдера"""
        file = FileSnapshot(hash="test_lc_error", path="/tmp/test_lc_error.txt", status_sync="added")
        
        mock_provider = Mock()
        mock_provider.embed_documents.side_effect = Exception("Provider error")
        
        result = langchain_embedding(test_db, file, ["Чанк"], provider=mock_provider)
        assert result == 0
    
    def test_langchain_mismatched_vectors(self, test_db):
        """Тест когда количество векторов не совпадает с чанками"""
        file = FileSnapshot(hash="test_lc_mismatch", path="/tmp/test_lc_mismatch.txt", status_sync="added")
        
        mock_provider = Mock()
        mock_provider.embed_documents.return_value = [[0.1] * 1024]  # 1 вектор для 2 чанков
        
        result = langchain_embedding(test_db, file, ["Чанк 1", "Чанк 2"], provider=mock_provider)
        assert result == 0
    
    def test_langchain_deletes_old_chunks(self, test_db):
        """Тест что старые чанки удаляются перед вставкой"""
        file_hash = "test_lc_delete_old"
        file_path = "/tmp/test_lc_delete_old.txt"
        file = FileSnapshot(hash=file_hash, path=file_path, status_sync="added")
        
        mock_provider = Mock()
        
        # Первая вставка - 3 чанка
        mock_provider.embed_documents.return_value = [[0.1] * 1024, [0.2] * 1024, [0.3] * 1024]
        result1 = langchain_embedding(test_db, file, ["A", "B", "C"], provider=mock_provider)
        assert result1 == 3
        
        # Вторая вставка - 2 чанка
        mock_provider.embed_documents.return_value = [[0.4] * 1024, [0.5] * 1024]
        result2 = langchain_embedding(test_db, file, ["X", "Y"], provider=mock_provider)
        assert result2 == 2
        
        # Проверяем что только 2 новых чанка
        with test_db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT content FROM chunks WHERE metadata->>'file_hash' = %s ORDER BY metadata->>'chunk_index'",
                    (file_hash,)
                )
                contents = [row[0] for row in cur.fetchall()]
                assert contents == ["X", "Y"]
