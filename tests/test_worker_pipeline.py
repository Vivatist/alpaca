"""
Тесты пайплайна обработки файлов
"""
import pytest
import os
import json
import tempfile
from unittest.mock import MagicMock
import responses

from settings import settings
from core.domain.files.models import FileSnapshot


def ollama_embed_callback(request):
    """Возвращает N эмбеддингов для N текстов"""
    body = json.loads(request.body)
    texts = body.get("input", [])
    if isinstance(texts, str):
        texts = [texts]
    embeddings = [[0.1] * 1024 for _ in texts]
    return (200, {}, json.dumps({"embeddings": embeddings}))


class TestWorkerPipeline:
    """Тесты полного пайплайна обработки"""
    
    @responses.activate
    def test_pipeline_docx_to_chunks(self, test_db, temp_docx_file, cleanup_temp_parsed, ingest_pipeline):
        """Тест полного пайплайна: DOCX → парсинг → чанки → эмбеддинги"""
        # Mock Ollama API (batch endpoint) — возвращает N эмбеддингов для N текстов
        responses.add_callback(
            responses.POST,
            f"{settings.OLLAMA_BASE_URL}/api/embed",
            callback=ollama_embed_callback,
            content_type="application/json",
        )
        
        file_hash = "test_full_pipeline_123"
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
        
        # Проверяем что файл обработан
        with test_db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT status_sync FROM files WHERE hash = %s", (file_hash,))
                row = cur.fetchone()
                if row:
                    assert row[0] == "ok"
                
                # Проверяем что созданы чанки
                cur.execute(
                    "SELECT COUNT(*) FROM chunks WHERE metadata->>'file_hash' = %s",
                    (file_hash,)
                )
                chunks_count = cur.fetchone()[0]
                assert chunks_count > 0
    
    def test_pipeline_unsupported_file_type(self, test_db, ingest_pipeline):
        """Тест обработки неподдерживаемого типа файла"""
        file_hash = "test_unsupported_123"
        file_path = "/tmp/test_file.pdf"  # PDF не поддерживается
        
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
                row = cur.fetchone()
                if row:
                    assert row[0] == "error"
    
    @responses.activate
    def test_pipeline_empty_parsed_text(self, test_db, temp_docx_file, ingest_pipeline, monkeypatch):
        """Тест обработки файла с пустым результатом парсинга"""
        from core.application.document_processing.parsers import WordParser
        monkeypatch.setattr(WordParser, "_parse", MagicMock(return_value=""))
        
        file_hash = "test_empty_parsed_123"
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
        
        # Проверяем статус
        with test_db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT status_sync FROM files WHERE hash = %s", (file_hash,))
                row = cur.fetchone()
                if row:
                    assert row[0] == "error"
    
    @responses.activate
    def test_pipeline_no_chunks_created(self, test_db, temp_docx_file, ingest_pipeline, monkeypatch):
        """Тест когда чанкование не создаёт чанков"""
        from core.application.document_processing.parsers import WordParser
        monkeypatch.setattr(WordParser, "_parse", MagicMock(return_value="Текст был распарсен"))
        ingest_pipeline.chunker = lambda _file: []
        
        file_hash = "test_no_chunks_123"
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
    
    @responses.activate
    def test_pipeline_creates_temp_file(self, test_db, temp_docx_file, cleanup_temp_parsed, ingest_pipeline, monkeypatch):
        """Тест что пайплайн создаёт временный .md файл"""
        test_text = "Тестовый текст для сохранения"
        from core.application.document_processing.parsers import WordParser
        monkeypatch.setattr(WordParser, "_parse", MagicMock(return_value=test_text))
        
        # Mock Ollama (batch endpoint) — возвращает N эмбеддингов для N текстов
        responses.add_callback(
            responses.POST,
            f"{settings.OLLAMA_BASE_URL}/api/embed",
            callback=ollama_embed_callback,
            content_type="application/json",
        )
        
        file_hash = "test_temp_file_123"
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
        
        # Проверяем что создан временный файл
        temp_dir = "/home/alpaca/tmp_md"
        temp_file = os.path.join(temp_dir, f"{file_path}.md")
        assert os.path.exists(temp_file)
        
        # Проверяем содержимое
        with open(temp_file, 'r', encoding='utf-8') as f:
            content = f.read()
            assert content == test_text
