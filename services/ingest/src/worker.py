"""
Worker - управление параллельной обработкой файлов.

Опрашивает FileWatcher API и обрабатывает файлы в пуле потоков.
"""

import time
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Optional, Dict, Any

from logging_config import get_logger
from contracts import Repository
from settings import settings

logger = get_logger("ingest.worker")


class Worker:
    """Менеджер параллельной обработки файлов."""
    
    def __init__(
        self,
        repository: Repository,
        filewatcher_api_url: str,
        process_file_func: Callable[[Dict[str, Any]], bool]
    ):
        """
        Args:
            repository: Репозиторий для работы с БД
            filewatcher_api_url: URL API FileWatcher
            process_file_func: Функция обработки файла
        """
        self.repository = repository
        self.filewatcher_api_url = filewatcher_api_url
        self.process_file = process_file_func
        self.processed_count = 0
        
        # Проверяем доступность FileWatcher API при инициализации
        try:
            response = requests.get(
                f"{self.filewatcher_api_url}/api/queue/stats",
                timeout=5
            )
            response.raise_for_status()
            logger.info(f"✅ FileWatcher API is available at {self.filewatcher_api_url}")
        except requests.exceptions.ConnectionError:
            logger.error(f"❌ Cannot connect to FileWatcher API at {self.filewatcher_api_url}")
            logger.error(f"   Make sure FileWatcher service is running")
            raise
        except requests.exceptions.Timeout:
            logger.error(f"❌ FileWatcher API timeout at {self.filewatcher_api_url}")
            logger.error(f"   Make sure FileWatcher service is responding")
            raise
        except Exception as e:
            logger.error(f"❌ Failed to check FileWatcher API: {e}")
            raise
    
    def _get_next_file(self) -> Optional[Dict[str, Any]]:
        """Получить следующий файл из очереди FileWatcher."""
        try:
            response = requests.get(
                f"{self.filewatcher_api_url}/api/next-file",
                timeout=5
            )
            if response.status_code == 204:
                return None  # Очередь пуста
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get next file | error={e}")
            return None
    
    def start(
        self, 
        poll_interval: int = 5, 
        max_workers: int = 5
    ):
        """
        Запустить worker с параллельной обработкой.
        
        Args:
            poll_interval: Интервал опроса очереди в секундах
            max_workers: Максимальное количество параллельных задач
        """
        logger.info(f"🚀 Starting worker | max_workers={max_workers} poll_interval={poll_interval}s")
        
        with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="ingest") as executor:
            futures = {}  # future -> file_path mapping
            
            while True:
                try:
                    # Удаляем завершённые задачи
                    done_futures = [f for f in list(futures.keys()) if f.done()]
                    for future in done_futures:
                        file_path = futures[future]
                        try:
                            success = future.result()
                            if success:
                                self.processed_count += 1
                                logger.info(f"📊 Total processed: {self.processed_count}")
                        except Exception as e:
                            logger.error(f"Task failed | path={file_path} error={e}")
                        del futures[future]
                    
                    # Если есть свободные слоты, берём новые файлы
                    while len(futures) < max_workers:
                        file_info = self._get_next_file()
                        
                        if file_info is None:
                            break  # Очередь пуста
                        
                        # Помечаем файл как processed СРАЗУ
                        self.repository.mark_as_processed(file_info['hash'])
                        
                        # Запускаем обработку в отдельном потоке
                        future = executor.submit(self.process_file, file_info)
                        futures[future] = file_info['path']
                    
                    # Ждём
                    if not futures:
                        logger.debug("Queue is empty, waiting...")
                        time.sleep(poll_interval)
                    elif file_info is None:
                        # Есть активные задачи, но очередь пуста - ждём подольше
                        time.sleep(poll_interval)
                    else:
                        # Есть и задачи, и файлы в очереди - быстрый цикл
                        time.sleep(0.2)
                        
                except KeyboardInterrupt:
                    logger.info("Shutting down worker...")
                    logger.info(f"Waiting for {len(futures)} active tasks...")
                    for future in as_completed(futures.keys()):
                        try:
                            future.result()
                        except Exception:
                            pass
                    break
                except Exception as e:
                    logger.error(f"Unexpected error in worker loop: {e}")
                    time.sleep(poll_interval)
        
        logger.info(f"Worker stopped. Total processed: {self.processed_count}")
