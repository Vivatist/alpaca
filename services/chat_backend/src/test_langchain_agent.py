#!/usr/bin/env python3
"""
Тестовый скрипт для проверки LangChain Agent RAG.

Запуск:
1. Установить зависимости: pip install -r requirements-langchain.txt
2. Запустить: python test_langchain_agent.py

Для тестирования внутри Docker:
docker exec -it alpaca-chat-backend-1 pip install langchain-ollama langgraph langchain-core
docker exec -it alpaca-chat-backend-1 python /app/src/test_langchain_agent.py
"""

import sys
import os

# Добавляем путь к src
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Мокаем settings для локального запуска
class MockSettings:
    OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_LLM_MODEL = os.getenv("OLLAMA_LLM_MODEL", "qwen2.5:32b")
    LLM_BACKEND = "langchain_agent"

# Патчим settings
import settings as settings_module
settings_module.settings = MockSettings()


def mock_search(query: str):
    """Мок функции поиска для тестирования."""
    print(f"🔍 Mock search called with: {query}")
    return [
        {
            "content": "ALPACA — это RAG система для работы с документами компании. "
                      "Она позволяет искать информацию в документах и отвечать на вопросы.",
            "metadata": {
                "file_path": "docs/README.md",
                "title": "ALPACA RAG System",
                "chunk_index": 0,
            },
            "similarity": 0.95,
        },
        {
            "content": "Система использует Ollama для генерации эмбеддингов и ответов. "
                      "Документы хранятся в PostgreSQL с расширением pgvector.",
            "metadata": {
                "file_path": "docs/architecture.md", 
                "title": "Architecture",
                "chunk_index": 1,
            },
            "similarity": 0.85,
        },
    ]


def test_sync():
    """Тест синхронной генерации."""
    print("\n" + "="*60)
    print("TEST: Синхронная генерация")
    print("="*60)
    
    from llm.langchain_agent import generate_response, set_search_function
    
    set_search_function(mock_search)
    
    response = generate_response(
        prompt="Что такое ALPACA?",
        system_prompt="Ты полезный ассистент. Используй инструмент поиска для ответа на вопросы.",
    )
    
    print(f"\nОтвет:\n{response}")


def test_stream():
    """Тест потоковой генерации."""
    print("\n" + "="*60)
    print("TEST: Потоковая генерация")
    print("="*60)
    
    from llm.langchain_agent import generate_response_stream, set_search_function
    
    set_search_function(mock_search)
    
    print("\nОтвет (streaming):")
    for chunk in generate_response_stream(
        prompt="Расскажи про архитектуру системы ALPACA",
        system_prompt="Ты полезный ассистент. Используй инструмент поиска для ответа на вопросы.",
    ):
        print(chunk, end="", flush=True)
    print("\n")


def test_without_tools():
    """Тест без использования инструментов."""
    print("\n" + "="*60)
    print("TEST: Простой вопрос (без инструментов)")
    print("="*60)
    
    from llm.langchain_agent import generate_response_stream
    
    print("\nОтвет (streaming):")
    for chunk in generate_response_stream(
        prompt="Сколько будет 2+2?",
        system_prompt="Отвечай кратко.",
    ):
        print(chunk, end="", flush=True)
    print("\n")


if __name__ == "__main__":
    print("🧪 Тестирование LangChain Agent RAG")
    print(f"📡 Ollama URL: {MockSettings.OLLAMA_BASE_URL}")
    print(f"🤖 Model: {MockSettings.OLLAMA_LLM_MODEL}")
    
    # Проверяем доступность LangChain
    try:
        from langchain_ollama import ChatOllama
        from langgraph.prebuilt import create_react_agent
        print("✅ LangChain dependencies available")
    except ImportError as e:
        print(f"❌ LangChain not installed: {e}")
        print("\nУстановите зависимости:")
        print("pip install langchain-ollama langgraph langchain-core")
        sys.exit(1)
    
    # Запускаем тесты
    try:
        test_without_tools()
        test_sync()
        test_stream()
        print("\n✅ Все тесты завершены!")
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
