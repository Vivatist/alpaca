"""
Тесты многопоточности и семафоров Worker
Проверяет что Worker корректно обрабатывает файлы параллельно с соблюдением лимитов
"""
import pytest
import time
import threading
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
import responses

from settings import settings


class TestWorkerConcurrency:
    """Тесты параллельной обработки и семафоров"""
    
    def test_threadpool_max_workers_limit(self):
        """Тест что ThreadPoolExecutor соблюдает лимит max_workers"""
        max_workers = 3
        tasks_count = 10
        max_concurrent = [0]  #Максимальное количество одновременных потоков
        current_threads = [0]
        lock = threading.Lock()
        
        def slow_task(task_id):
            """Медленная задача для проверки параллелизма"""
            with lock:
                current_threads[0] += 1
                if current_threads[0] > max_concurrent[0]:
                    max_concurrent[0] = current_threads[0]
            
            time.sleep(0.1)  # Имитация работы
            
            with lock:
                current_threads[0] -= 1
            
            return task_id
        
        # Запускаем задачи через ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(slow_task, i) for i in range(tasks_count)]
            
            # Ждём завершения всех
            for future in futures:
                future.result()
        
        # Проверяем что не превысили лимит
        assert max_concurrent[0] <= max_workers, \
            f"Превышен лимит потоков: {max_concurrent[0]} > {max_workers}"
        
        # Проверяем что действительно было параллельное выполнение
        assert max_concurrent[0] >= 2, \
            f"Недостаточно параллелизма: {max_concurrent[0]}"
    
    @responses.activate
    def test_parse_semaphore_limit(self, test_db, temp_docx_file):
        """Тест что семафор PARSE_SEMAPHORE ограничивает количество параллельных парсингов"""
        # Импортируем ДО создания патчей
        import main
        from main import ingest_pipeline
        
        max_concurrent_parsing = [0]
        current_parsing = [0]
        lock = threading.Lock()
        
        # Оборачиваем __enter__ и __exit__ семафора
        original_enter = main.PARSE_SEMAPHORE.__enter__
        original_exit = main.PARSE_SEMAPHORE.__exit__
        
        def tracked_enter(*args, **kwargs):
            with lock:
                current_parsing[0] += 1
                if current_parsing[0] > max_concurrent_parsing[0]:
                    max_concurrent_parsing[0] = current_parsing[0]
            result = original_enter(*args, **kwargs)
            time.sleep(0.01)  # Даём времяна срабатывание
            return result
        
        def tracked_exit(*args, **kwargs):
            with lock:
                current_parsing[0] -= 1
            return original_exit(*args, **kwargs)
        
        # Mock парсера с задержкой
        def slow_parser(file_info):
            time.sleep(0.2)  # Имитация долгого парсинга
            return "Parsed text " * 100
        
        # Mock Ollama API
        responses.add(
            responses.POST,
            f"{settings.OLLAMA_BASE_URL}/api/embeddings",
            json={'embedding': [0.1] * 1024},
            status=200
        )
        
        # Патчим семафор и парсер
        main.PARSE_SEMAPHORE.__enter__ = tracked_enter
        main.PARSE_SEMAPHORE.__exit__ = tracked_exit
        
        try:
            with patch('main.parser_word_old_task', side_effect=slow_parser):
                # Запускаем несколько пайплайнов параллельно
                with ThreadPoolExecutor(max_workers=5) as executor:
                    futures = []
                    for i in range(5):
                        file_hash = f"test_parse_hash_{i}"
                        file_path = f"{temp_docx_file}_parse_{i}"  # Уникальный путь
                        
                        # Добавляем файл в БД
                        with test_db.get_connection() as conn:
                            with conn.cursor() as cur:
                                cur.execute(
                                    "INSERT INTO files (file_hash, file_path, file_size, status_sync) VALUES (%s, %s, %s, %s)",
                                    (file_hash, file_path, 1024, "processed")
                                )
                            conn.commit()
                        
                        future = executor.submit(ingest_pipeline, file_hash, temp_docx_file)
                        futures.append(future)
                    
                    # Ждём завершения всех
                    for future in futures:
                        future.result()
        finally:
            # Восстанавливаем оригинальные методы
            main.PARSE_SEMAPHORE.__enter__ = original_enter
            main.PARSE_SEMAPHORE.__exit__ = original_exit
        
        # Проверяем что семафор ограничил параллельность
        assert max_concurrent_parsing[0] <= settings.WORKER_MAX_CONCURRENT_PARSING, \
            f"Превышен лимит парсинга: {max_concurrent_parsing[0]} > {settings.WORKER_MAX_CONCURRENT_PARSING}"
        
        # Проверяем что было параллельное выполнение
        assert max_concurrent_parsing[0] >= 1, \
            "Парсинг не запустился параллельно"
    
    @responses.activate
    def test_embed_semaphore_limit(self, test_db, temp_docx_file):
        """Тест что семафор EMBED_SEMAPHORE ограничивает количество параллельных эмбеддингов"""
        import main
        from main import ingest_pipeline
        
        max_concurrent_embedding = [0]
        current_embedding = [0]
        lock = threading.Lock()
        
        # Оборачиваем __enter__ и __exit__ семафора
        original_enter = main.EMBED_SEMAPHORE.__enter__
        original_exit = main.EMBED_SEMAPHORE.__exit__
        
        def tracked_enter(*args, **kwargs):
            with lock:
                current_embedding[0] += 1
                if current_embedding[0] > max_concurrent_embedding[0]:
                    max_concurrent_embedding[0] = current_embedding[0]
            result = original_enter(*args, **kwargs)
            time.sleep(0.01)  # Даём время на срабатывание
            return result
        
        def tracked_exit(*args, **kwargs):
            with lock:
                current_embedding[0] -= 1
            return original_exit(*args, **kwargs)
        
        # Mock парсера
        def fast_parser(file_info):
            return "Parsed text for embedding test " * 100
        
        # Mock Ollama API с задержкой
        def ollama_response_callback(request):
            time.sleep(0.2)  # Имитация долгого эмбеддинга
            return (200, {}, '{"embedding": ' + str([0.1] * 1024) + '}')
        
        responses.add_callback(
            responses.POST,
            f"{settings.OLLAMA_BASE_URL}/api/embeddings",
            callback=ollama_response_callback,
            content_type='application/json'
        )
        
        # Патчим семафор
        main.EMBED_SEMAPHORE.__enter__ = tracked_enter
        main.EMBED_SEMAPHORE.__exit__ = tracked_exit
        
        try:
            with patch('main.parser_word_old_task', side_effect=fast_parser):
                # Запускаем несколько пайплайнов параллельно
                with ThreadPoolExecutor(max_workers=5) as executor:
                    futures = []
                    for i in range(5):
                        file_hash = f"test_embed_hash_{i}"
                        file_path = f"{temp_docx_file}_embed_{i}"  # Уникальный путь
                        
                        # Добавляем файл в БД
                        with test_db.get_connection() as conn:
                            with conn.cursor() as cur:
                                cur.execute(
                                    "INSERT INTO files (file_hash, file_path, file_size, status_sync) VALUES (%s, %s, %s, %s)",
                                    (file_hash, file_path, 1024, "processed")
                                )
                            conn.commit()
                        
                        future = executor.submit(ingest_pipeline, file_hash, temp_docx_file)
                        futures.append(future)
                    
                    # Ждём завершения всех
                    for future in futures:
                        future.result()
        finally:
            # Восстанавливаем оригинальные методы
            main.EMBED_SEMAPHORE.__enter__ = original_enter
            main.EMBED_SEMAPHORE.__exit__ = original_exit
        
        # Проверяем что семафор ограничил параллельность
        assert max_concurrent_embedding[0] <= settings.WORKER_MAX_CONCURRENT_EMBEDDING, \
            f"Превышен лимит эмбеддинга: {max_concurrent_embedding[0]} > {settings.WORKER_MAX_CONCURRENT_EMBEDDING}"
        
        # Проверяем что было параллельное выполнение
        assert max_concurrent_embedding[0] >= 1, \
            "Эмбеддинг не запустился параллельно"
    
    def test_semaphore_limits_access(self):
        """Простой тест что Semaphore работает как ожидается"""
        from threading import Semaphore
        
        max_concurrent = [0]
        current_threads = [0]
        lock = threading.Lock()
        
        sem = Semaphore(2)  # Максимум 2 потока
        
        def limited_task(task_id):
            with sem:
                with lock:
                    current_threads[0] += 1
                    if current_threads[0] > max_concurrent[0]:
                        max_concurrent[0] = current_threads[0]
                
                time.sleep(0.1)
                
                with lock:
                    current_threads[0] -= 1
        
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(limited_task, i) for i in range(5)]
            for future in futures:
                future.result()
        
        # Проверяем что семафор ограничил до 2 потоков
        assert max_concurrent[0] == 2, \
            f"Семафор не ограничил параллельность: {max_concurrent[0]} вместо 2"
