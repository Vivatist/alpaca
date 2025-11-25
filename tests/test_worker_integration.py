"""
Интеграционные тесты для worker
"""
import pytest
import os
import hashlib
from unittest.mock import Mock, patch, MagicMock
import responses

from worker import process_deleted_file, ingest_pipeline, process_file
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
                    "INSERT INTO files (file_hash, file_path, file_size, status_sync) VALUES (%s, %s, %s, %s)",
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
        
        # Удаляем
        result = process_deleted_file(file_hash, file_path)
        
        assert result is True
        
        # Проверяем что файл удалён
        with test_db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM files WHERE file_hash = %s", (file_hash,))
                assert cur.fetchone()[0] == 0
                
                cur.execute(
                    "SELECT COUNT(*) FROM chunks WHERE metadata->>'file_hash' = %s",
                    (file_hash,)
                )
                assert cur.fetchone()[0] == 0
    
    @responses.activate
    @patch('worker.parser_word_old_task')
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
                    "INSERT INTO files (file_hash, file_path, file_size, status_sync) VALUES (%s, %s, %s, %s)",
                    (file_hash, file_path, 1024, "processed")
                )
            conn.commit()
        
        result = ingest_pipeline(file_hash, file_path)
        
        assert result is True
        
        # Проверяем что файл помечен как ok
        with test_db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT status_sync FROM files WHERE file_hash = %s", (file_hash,))
                status = cur.fetchone()
                if status:
                    assert status[0] == "ok"
    
    @patch('worker.parser_word_old_task')
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
                    "INSERT INTO files (file_hash, file_path, file_size, status_sync) VALUES (%s, %s, %s, %s)",
                    (file_hash, file_path, 1024, "processed")
                )
            conn.commit()
        
        result = ingest_pipeline(file_hash, file_path)
        
        assert result is False
        
        # Проверяем что файл помечен как error
        with test_db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT status_sync FROM files WHERE file_hash = %s", (file_hash,))
                status = cur.fetchone()
                if status:
                    assert status[0] == "error"
    
    @responses.activate
    @patch('worker.ingest_pipeline')
    def test_process_file_added(self, mock_ingest, test_db, mock_file_info):
        """Тест обработки добавленного файла"""
        mock_ingest.return_value = True
        
        file_info = mock_file_info("/tmp/test_added.docx", "hash_added_123", "added")
        
        result = process_file(file_info)
        
        assert result is True
        assert mock_ingest.called
        assert mock_ingest.call_count == 1
    
    @responses.activate
    @patch('worker.process_deleted_file')
    def test_process_file_deleted(self, mock_delete, test_db, mock_file_info):
        """Тест обработки удалённого файла"""
        mock_delete.return_value = True
        
        file_info = mock_file_info("/tmp/test_deleted.docx", "hash_deleted_123", "deleted")
        
        result = process_file(file_info)
        
        assert result is True
        assert mock_delete.called
        assert mock_delete.call_count == 1
    
    @responses.activate
    @patch('worker.process_deleted_file')
    @patch('worker.ingest_pipeline')
    def test_process_file_updated(self, mock_ingest, mock_delete, test_db, mock_file_info):
        """Тест обработки обновлённого файла"""
        mock_delete.return_value = True
        mock_ingest.return_value = True
        
        file_info = mock_file_info("/tmp/test_updated.docx", "hash_updated_123", "updated")
        
        result = process_file(file_info)
        
        assert result is True
        # Для updated должны вызваться оба метода
        assert mock_delete.called
        assert mock_ingest.called
    
    def test_process_file_unknown_status(self, test_db, mock_file_info):
        """Тест обработки файла с неизвестным статусом"""
        file_info = mock_file_info("/tmp/test_unknown.docx", "hash_unknown_123", "unknown_status")
        
        result = process_file(file_info)
        
        assert result is False
