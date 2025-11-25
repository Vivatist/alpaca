"""
Pytest fixtures для тестирования воркера
"""
import os
import tempfile
import pytest
import psycopg2
import logging
from pathlib import Path
from typing import Generator

from utils.database import PostgreDatabase
from settings import settings


@pytest.fixture(scope="session", autouse=True)
def setup_test_logging():
    """Настройка логирования для тестов - изолированно от основного приложения"""
    # Настраиваем логирование для тестов
    root_logger = logging.getLogger()
    
    # Очищаем все существующие handlers
    root_logger.handlers.clear()
    
    # Создаём новый handler для тестов
    handler = logging.StreamHandler()
    handler.setLevel(logging.ERROR)  # В тестах показываем только ошибки
    formatter = logging.Formatter('%(asctime)s | %(levelname)-8s | %(name)s - %(message)s')
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.ERROR)
    
    yield
    
    # После тестов НЕ восстанавливаем handlers - они будут созданы заново
    # при следующем вызове setup_logging() в основном приложении
    root_logger.handlers.clear()


@pytest.fixture
def test_db() -> Generator[PostgreDatabase, None, None]:
    """Создание тестовой БД"""
    db = PostgreDatabase(settings.DATABASE_URL)
    yield db
    # Cleanup после тестов
    with db.get_connection() as conn:
        with conn.cursor() as cur:
            # Очистка тестовых данных
            cur.execute("DELETE FROM chunks WHERE metadata->>'file_path' LIKE '/tmp/test_%'")
            cur.execute("DELETE FROM files WHERE file_path LIKE '/tmp/test_%'")
        conn.commit()


@pytest.fixture
def temp_test_file() -> Generator[tuple[str, str], None, None]:
    """Создание временного тестового файла"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', prefix='test_', delete=False) as f:
        test_content = "Это тестовый файл.\n\nОн содержит несколько параграфов.\n\nДля проверки работы чанкования."
        f.write(test_content)
        temp_path = f.name
    
    yield temp_path, test_content
    
    # Cleanup
    if os.path.exists(temp_path):
        os.unlink(temp_path)


@pytest.fixture
def temp_docx_file() -> Generator[str, None, None]:
    """Создание временного DOCX файла для тестирования парсинга"""
    from docx import Document
    
    with tempfile.NamedTemporaryFile(mode='wb', suffix='.docx', prefix='test_', delete=False) as f:
        doc = Document()
        doc.add_paragraph("Заголовок тестового документа")
        doc.add_paragraph("Это первый параграф с тестовым содержимым.")
        doc.add_paragraph("Это второй параграф.")
        doc.add_paragraph("А это третий параграф с дополнительным текстом для проверки парсинга.")
        doc.save(f.name)
        temp_path = f.name
    
    yield temp_path
    
    # Cleanup
    if os.path.exists(temp_path):
        os.unlink(temp_path)


@pytest.fixture
def mock_file_info():
    """Создание мока информации о файле"""
    def _create_mock(file_path: str, file_hash: str, status: str = 'added'):
        return {
            'file_path': file_path,
            'file_hash': file_hash,
            'status_sync': status
        }
    return _create_mock


@pytest.fixture
def cleanup_temp_parsed():
    """Очистка временных распарсенных файлов"""
    temp_dir = "/home/alpaca/tmp_md"
    yield
    # Cleanup после тестов
    if os.path.exists(temp_dir):
        for file in Path(temp_dir).rglob("test_*"):
            if file.is_file():
                file.unlink()
