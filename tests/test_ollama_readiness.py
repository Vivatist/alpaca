"""
Тесты проверки готовности моделей Ollama.

Эти тесты критически важны и запускаются перед стартом worker.
Проверяют:
1. Доступность эмбеддинг модели (bge-m3)
2. Ответ LLM модели (qwen2.5:32b)
"""

import pytest
import requests
from settings import settings


class TestOllamaReadiness:
    """Тесты готовности Ollama моделей."""
    
    def test_embedding_model_ready(self):
        """Проверка готовности эмбеддинг модели.
        
        Отправляет тестовый запрос к API эмбеддингов и проверяет:
        - Сервер Ollama доступен
        - Модель bge-m3 загружена
        - Возвращается вектор правильной размерности (1024)
        """
        url = f"{settings.OLLAMA_BASE_URL}/api/embed"
        payload = {
            "model": settings.OLLAMA_EMBEDDING_MODEL,
            "input": "Тестовый текст для проверки эмбеддинга"
        }
        
        try:
            response = requests.post(url, json=payload, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            # Проверяем наличие эмбеддинга
            assert "embeddings" in data, "Ответ не содержит поле 'embeddings'"
            assert len(data["embeddings"]) > 0, "Массив embeddings пуст"
            
            embedding = data["embeddings"][0]
            
            # Проверяем размерность (bge-m3 = 1024)
            assert len(embedding) == 1024, (
                f"Неверная размерность эмбеддинга: {len(embedding)}, ожидалось 1024"
            )
            
            # Проверяем что значения числовые
            assert all(isinstance(x, (int, float)) for x in embedding[:10]), (
                "Эмбеддинг содержит нечисловые значения"
            )
            
        except requests.exceptions.ConnectionError:
            pytest.fail(
                f"❌ Ollama недоступен по адресу {settings.OLLAMA_BASE_URL}. "
                "Убедитесь что сервис запущен."
            )
        except requests.exceptions.Timeout:
            pytest.fail(
                f"❌ Таймаут при запросе к Ollama. "
                f"Модель {settings.OLLAMA_EMBEDDING_MODEL} может быть не загружена."
            )
        except requests.exceptions.HTTPError as e:
            pytest.fail(
                f"❌ HTTP ошибка от Ollama: {e}. "
                f"Проверьте что модель {settings.OLLAMA_EMBEDDING_MODEL} установлена: "
                f"ollama pull {settings.OLLAMA_EMBEDDING_MODEL}"
            )
    
    def test_llm_model_ready(self):
        """Проверка готовности LLM модели для генерации.
        
        Отправляет простой запрос к API генерации и проверяет:
        - Сервер Ollama доступен
        - LLM модель загружена и отвечает
        - Ответ содержит сгенерированный текст
        """
        url = f"{settings.OLLAMA_BASE_URL}/api/generate"
        payload = {
            "model": settings.OLLAMA_LLM_MODEL,
            "prompt": "Ответь одним словом: 2+2=",
            "stream": False,
            "options": {
                "temperature": 0,
                "num_predict": 10  # Ограничиваем ответ для быстроты
            }
        }
        
        try:
            response = requests.post(url, json=payload, timeout=60)
            response.raise_for_status()
            
            data = response.json()
            
            # Проверяем наличие ответа
            assert "response" in data, "Ответ не содержит поле 'response'"
            assert len(data["response"].strip()) > 0, "LLM вернул пустой ответ"
            
            # Проверяем что генерация завершилась
            assert data.get("done", False), "Генерация не завершена (done=false)"
            
        except requests.exceptions.ConnectionError:
            pytest.fail(
                f"❌ Ollama недоступен по адресу {settings.OLLAMA_BASE_URL}. "
                "Убедитесь что сервис запущен."
            )
        except requests.exceptions.Timeout:
            pytest.fail(
                f"❌ Таймаут при запросе к LLM. "
                f"Модель {settings.OLLAMA_LLM_MODEL} может загружаться или быть слишком медленной."
            )
        except requests.exceptions.HTTPError as e:
            pytest.fail(
                f"❌ HTTP ошибка от Ollama: {e}. "
                f"Проверьте что модель {settings.OLLAMA_LLM_MODEL} установлена: "
                f"ollama pull {settings.OLLAMA_LLM_MODEL}"
            )
    
    def test_ollama_models_available(self):
        """Проверка что требуемые модели установлены в Ollama.
        
        Запрашивает список моделей и проверяет наличие:
        - Эмбеддинг модели (bge-m3)
        - LLM модели (qwen2.5:32b)
        """
        url = f"{settings.OLLAMA_BASE_URL}/api/tags"
        
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            models = [m["name"] for m in data.get("models", [])]
            
            # Проверяем эмбеддинг модель
            embedding_model = settings.OLLAMA_EMBEDDING_MODEL
            embedding_found = any(embedding_model in m for m in models)
            assert embedding_found, (
                f"❌ Эмбеддинг модель '{embedding_model}' не найдена. "
                f"Доступные модели: {models}. "
                f"Установите: ollama pull {embedding_model}"
            )
            
            # Проверяем LLM модель
            llm_model = settings.OLLAMA_LLM_MODEL
            llm_found = any(llm_model in m for m in models)
            assert llm_found, (
                f"❌ LLM модель '{llm_model}' не найдена. "
                f"Доступные модели: {models}. "
                f"Установите: ollama pull {llm_model}"
            )
            
        except requests.exceptions.ConnectionError:
            pytest.fail(
                f"❌ Ollama недоступен по адресу {settings.OLLAMA_BASE_URL}. "
                "Убедитесь что сервис запущен."
            )
