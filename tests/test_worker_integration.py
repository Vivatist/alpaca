"""
Интеграционные тесты для worker
"""
import pytest
import os
import hashlib
import json
from unittest.mock import MagicMock
import responses

from settings import settings
from core.domain.files.models import FileSnapshot


def ollama_embed_callback(request):
    """Callback для мока Ollama /api/embed — возвращает N эмбеддингов для N текстов"""
    body = json.loads(request.body)
    texts = body.get("input", [])
    if isinstance(texts, str):
        texts = [texts]
    embeddings = [[0.1] * 1024 for _ in texts]
    return (200, {}, json.dumps({"embeddings": embeddings}))


class TestWorkerIntegration:
    """Интеграционные тесты worker"""
    
    def test_process_deleted_file(self, test_db, process_file_use_case):
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
        file_info = {"hash": file_hash, "path": file_path, "status_sync": "deleted"}
        result = process_file_use_case(file_info)
        
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
    def test_ingest_pipeline_success(self, test_db, temp_docx_file, cleanup_temp_parsed, ingest_pipeline, monkeypatch):
        """Тест успешного прохождения полного пайплайна"""
        # Mock парсера
        test_text = "Это тестовый текст для проверки пайплайна. " * 50
        from core.application.document_processing.parsers import WordParser
        monkeypatch.setattr(WordParser, "_parse", MagicMock(return_value=test_text))
        
        # Mock Ollama API (batch endpoint) — возвращает N эмбеддингов для N текстов
        responses.add_callback(
            responses.POST,
            f"{settings.OLLAMA_BASE_URL}/api/embed",
            callback=ollama_embed_callback,
            content_type="application/json",
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
        
        file = FileSnapshot(hash=file_hash, path=file_path, status_sync="added")
        result = ingest_pipeline(file)
        
        assert result is True
        
        # Проверяем что файл помечен как ok
        with test_db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT status_sync FROM files WHERE hash = %s", (file_hash,))
                status = cur.fetchone()
                if status:
                    assert status[0] == "ok"
    
    def test_ingest_pipeline_parse_error(self, test_db, temp_docx_file, ingest_pipeline, monkeypatch):
        """Тест обработки ошибки парсинга"""
        # Mock парсера с ошибкой
        from core.application.document_processing.parsers import WordParser
        monkeypatch.setattr(WordParser, "_parse", MagicMock(return_value=None))
        
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
        
        file = FileSnapshot(hash=file_hash, path=file_path, status_sync="added")
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
    def test_process_file_added(self, test_db, temp_docx_file, mock_file_info, process_file_use_case, monkeypatch):
        """Тест обработки добавленного файла"""
        mock_ingest = MagicMock(return_value=True)
        monkeypatch.setattr(process_file_use_case, "ingest_document", mock_ingest)
        
        file_info = mock_file_info("/tmp/test_added.docx", "hash_added_123", "added")
        
        result = process_file_use_case(file_info)
        
        assert result is True
        mock_ingest.assert_called_once()
    
    @responses.activate
    def test_process_file_deleted(self, test_db, mock_file_info, process_file_use_case):
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
        
        result = process_file_use_case(file_info)
        
        assert result is True
        
        # Проверяем что файл удалён
        with test_db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM files WHERE hash = %s", ("hash_deleted_123",))
                assert cur.fetchone()[0] == 0
    
    @responses.activate
    def test_process_file_updated(self, test_db, temp_docx_file, mock_file_info, process_file_use_case):
        """Тест обработки обновлённого файла"""
        # Мокаем Ollama API для эмбеддингов (batch endpoint) — возвращает N эмбеддингов
        responses.add_callback(
            responses.POST,
            "http://localhost:11434/api/embed",
            callback=ollama_embed_callback,
            content_type="application/json",
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
        
        result = process_file_use_case(file_info)
        
        assert result is True
        
        # Проверяем что файл помечен как ok
        with test_db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT status_sync FROM files WHERE hash = %s", ("hash_updated_123",))
                status = cur.fetchone()
                assert status[0] == "ok"
    
    def test_process_file_unknown_status(self, test_db, mock_file_info, process_file_use_case):
        """Тест обработки файла с неизвестным статусом"""
        file_info = mock_file_info("/tmp/test_unknown.docx", "hash_unknown_123", "unknown_status")
        
        result = process_file_use_case(file_info)
        
        assert result is False
