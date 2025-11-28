"""
Интеграционные тесты для worker
"""
import pytest
import os
import hashlib
from unittest.mock import Mock, patch, MagicMock
import responses

from main import ingest_pipeline, process_file
from settings import settings


class TestWorkerIntegration:
    """Интеграционные тесты worker"""
    
    def test_process_deleted_file(self, test_db):
        """Тест удаления файла и его чанков"""
        file_hash = "test_delete_hash_123"
        file_path = "/tmp/test_delete.txt"
        
        # Создаём тестовые данные
        with test_db.get_connection() as conn:
            with conn.cursor() as cur:
                # Добавляем файл
                cur.execute(
                    "INSERT INTO files (hash, path, size, status_sync) VALUES (%s, %s, %s, %s)",
                    (file_hash, file_path, 1024, "ok")
                )
                # Добавляем чанк
                import psycopg2.extras
                test_embedding = "[" + ",".join(["0.1"] * 1024) + "]"
                cur.execute(
                    """INSERT INTO chunks (content, metadata, embedding) 
                       VALUES (%s, %s, %s::vector)""",
                    ("Test content", psycopg2.extras.Json({"file_hash": file_hash}), test_embedding)
                )
            conn.commit()
        
        # Удаляем через process_file
        from utils.file_manager import File
        file_info = {"hash": file_hash, "path": file_path, "status_sync": "deleted"}
        result = process_file(file_info)
        
        assert result is True
        
        # Проверяем что файл удалён
        with test_db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM files WHERE hash = %s", (file_hash,))
                assert cur.fetchone()[0] == 0
                
                cur.execute(
                    "SELECT COUNT(*) FROM chunks WHERE metadata->>'file_hash' = %s",
                    (file_hash,)
                )
                assert cur.fetchone()[0] == 0
    
    @responses.activate
    @patch('main.parser_word_old_task')
    def test_ingest_pipeline_success(self, mock_parser, test_db, temp_docx_file, cleanup_temp_parsed):
        """Тест успешного прохождения полного пайплайна"""
        # Mock парсера
        test_text = "Это тестовый текст для проверки пайплайна. " * 50
        mock_parser.return_value = test_text
        
        # Mock Ollama API
        responses.add(
            responses.POST,
            f"{settings.OLLAMA_BASE_URL}/api/embeddings",
            json={'embedding': [0.1] * 1024},
            status=200
        )
        
        file_hash = "test_pipeline_hash_123"
        file_path = temp_docx_file
        
        # Добавляем файл в БД
        with test_db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO files (hash, path, size, status_sync) VALUES (%s, %s, %s, %s)",
                    (file_hash, file_path, 1024, "processed")
                )
            conn.commit()
        
        from utils.file_manager import File
        file = File(hash=file_hash, path=file_path, status_sync="added")
        result = ingest_pipeline(file)
        
        assert result is True
        
        # Проверяем что файл помечен как ok
        with test_db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT status_sync FROM files WHERE hash = %s", (file_hash,))
                status = cur.fetchone()
                if status:
                    assert status[0] == "ok"
    
    @patch('main.parser_word_old_task')
    def test_ingest_pipeline_parse_error(self, mock_parser, test_db, temp_docx_file):
        """Тест обработки ошибки парсинга"""
        # Mock парсера с ошибкой
        mock_parser.return_value = None
        
        file_hash = "test_error_hash_123"
        file_path = temp_docx_file
        
        # Добавляем файл в БД
        with test_db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO files (hash, path, size, status_sync) VALUES (%s, %s, %s, %s)",
                    (file_hash, file_path, 1024, "processed")
                )
            conn.commit()
        
        from utils.file_manager import File
        file = File(hash=file_hash, path=file_path, status_sync="added")
        result = ingest_pipeline(file)
        
        assert result is False
        
        # Проверяем что файл помечен как error
        with test_db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT status_sync FROM files WHERE hash = %s", (file_hash,))
                status = cur.fetchone()
                if status:
                    assert status[0] == "error"
    
    @responses.activate
    @patch('main.ingest_pipeline')
    def test_process_file_added(self, mock_ingest, test_db, temp_docx_file, mock_file_info):
        """Тест обработки добавленного файла"""
        mock_ingest.return_value = True
        
        file_info = mock_file_info("/tmp/test_added.docx", "hash_added_123", "added")
        
        result = process_file(file_info)
        
        assert result is True
        assert mock_ingest.called
        assert mock_ingest.call_count == 1
    
    @responses.activate
    def test_process_file_deleted(self, test_db, mock_file_info):
        """Тест обработки удалённого файла"""
        file_info = mock_file_info("/tmp/test_deleted.docx", "hash_deleted_123", "deleted")
        
        # Добавляем файл и чанки в БД для удаления
        with test_db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO files (hash, path, size, status_sync) VALUES (%s, %s, %s, %s)",
                    ("hash_deleted_123", "/tmp/test_deleted.docx", 1024, "deleted")
                )
            conn.commit()
        
        result = process_file(file_info)
        
        assert result is True
        
        # Проверяем что файл удалён
        with test_db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM files WHERE hash = %s", ("hash_deleted_123",))
                assert cur.fetchone()[0] == 0
    
    @responses.activate
    def test_process_file_updated(self, test_db, temp_docx_file, mock_file_info):
        """Тест обработки обновлённого файла"""
        # Мокаем Ollama API для эмбеддингов
        responses.add(
            responses.POST,
            "http://localhost:11434/api/embeddings",
            json={'embedding': [0.1] * 1024},
            status=200
        )
        
        file_info = mock_file_info(temp_docx_file, "hash_updated_123", "updated")
        
        # Добавляем файл и старые чанки в БД
        with test_db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO files (hash, path, size, status_sync) VALUES (%s, %s, %s, %s)",
                    ("hash_updated_123", temp_docx_file, 1024, "updated")
                )
            conn.commit()
        
        result = process_file(file_info)
        
        assert result is True
        
        # Проверяем что файл помечен как ok
        with test_db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT status_sync FROM files WHERE hash = %s", ("hash_updated_123",))
                status = cur.fetchone()
                assert status[0] == "ok"
    
    def test_process_file_unknown_status(self, test_db, mock_file_info):
        """Тест обработки файла с неизвестным статусом"""
        file_info = mock_file_info("/tmp/test_unknown.docx", "hash_unknown_123", "unknown_status")
        
        result = process_file(file_info)
        
        assert result is False
