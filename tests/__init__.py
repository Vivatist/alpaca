"""
Тесты для ALPACA Worker.

=== НАЗНАЧЕНИЕ ===
Pytest-набор тестов для проверки компонентов системы:
- test_chunker.py — тесты чанкера
- test_embedder.py — тесты эмбеддера
- test_parser.py — тесты парсеров
- test_worker_*.py — тесты worker'а

=== ЗАПУСК ===

    # Все тесты
    python tests/runner.py --suite all

    # Только unit-тесты
    python tests/runner.py --suite unit

    # Интеграционные
    python tests/runner.py --suite integration

    # Конкретный файл
    pytest tests/test_chunker.py -v

=== КОНФИГУРАЦИЯ ===
См. pytest.ini и conftest.py для fixtures.

=== НАСТРОЙКИ ===
settings.py:
- RUN_TESTS_ON_START = True  # запускать тесты при старте
- TEST_SUITE = "all"         # "unit", "integration", "all"
"""
