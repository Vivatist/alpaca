"""
Pytest configuration for Chat Backend.
"""
import sys
import os
from pathlib import Path

import pytest

# Загружаем тестовые ENV
env_file = Path(__file__).parent.parent / ".env.test"
if env_file.exists():
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ.setdefault(key, value)

# Добавляем src в путь
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))


@pytest.fixture
def test_client():
    """FastAPI test client."""
    from fastapi.testclient import TestClient
    from main import app
    return TestClient(app)
