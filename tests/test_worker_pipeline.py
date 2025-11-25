"""
Тесты пайплайна обработки файлов
"""
import pytest
import os
import tempfile
from unittest.mock import patch, MagicMock
import responses

from main import ingest_pipeline
from settings import settings


class TestWorkerPipeline:
    """Тесты полного пайплайна обработки"""
    
    @responses.activate
    def test_pipeline_docx_to_chunks(self, test_db, temp_docx_file, cleanup_temp_parsed):
        """Тест полного пайплайна: DOCX → парсинг → чанки → эмбеддинги"""
        # Mock Ollama API
        responses.add(
            responses.POST,
            f"{settings.OLLAMA_BASE_URL}/api/embeddings",
            json={'embedding': [0.1] * 1024},
            status=200
        )
        
        file_hash = "test_full_pipeline_123"
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
        
        # Проверяем что файл обработан
        with test_db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT status_sync FROM files WHERE file_hash = %s", (file_hash,))
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
    
    def test_pipeline_unsupported_file_type(self, test_db):
        """Тест обработки неподдерживаемого типа файла"""
        file_hash = "test_unsupported_123"
        file_path = "/tmp/test_file.pdf"  # PDF не поддерживается
        
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
                row = cur.fetchone()
                if row:
                    assert row[0] == "error"
    
    @responses.activate
    @patch('main.parser_word_old_task')
    def test_pipeline_empty_parsed_text(self, mock_parser, test_db, temp_docx_file):
        """Тест обработки файла с пустым результатом парсинга"""
        mock_parser.return_value = ""  # Пустой текст
        
        file_hash = "test_empty_parsed_123"
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
        
        # Проверяем статус
        with test_db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT status_sync FROM files WHERE file_hash = %s", (file_hash,))
                row = cur.fetchone()
                if row:
                    assert row[0] == "error"
    
    @responses.activate
    @patch('main.parser_word_old_task')
    @patch('main.chunking')
    def test_pipeline_no_chunks_created(self, mock_chunking, mock_parser, test_db, temp_docx_file):
        """Тест когда чанкование не создаёт чанков"""
        mock_parser.return_value = "Текст был распарсен"
        mock_chunking.return_value = []  # Пустой список чанков
        
        file_hash = "test_no_chunks_123"
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
    
    @responses.activate
    @patch('main.parser_word_old_task')
    def test_pipeline_creates_temp_file(self, mock_parser, test_db, temp_docx_file, cleanup_temp_parsed):
        """Тест что пайплайн создаёт временный .md файл"""
        test_text = "Тестовый текст для сохранения"
        mock_parser.return_value = test_text
        
        # Mock Ollama
        responses.add(
            responses.POST,
            f"{settings.OLLAMA_BASE_URL}/api/embeddings",
            json={'embedding': [0.1] * 1024},
            status=200
        )
        
        file_hash = "test_temp_file_123"
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
        
        # Проверяем что создан временный файл
        temp_dir = "/home/alpaca/tmp_md"
        temp_file = os.path.join(temp_dir, f"{file_path}.md")
        assert os.path.exists(temp_file)
        
        # Проверяем содержимое
        with open(temp_file, 'r', encoding='utf-8') as f:
            content = f.read()
            assert content == test_text
