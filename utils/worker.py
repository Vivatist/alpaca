"""
Worker - класс для управления параллельной обработкой файлов
Отвечает за управление потоками и координацию задач
"""
import time
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Optional, Dict, Any

from core.domain.files.repository import Database
from utils.logging import get_logger

logger = get_logger("core.worker.manager")



class Worker:
    """Менеджер параллельной обработки файлов"""
    
    def __init__(
        self,
        db: Database,
        filewatcher_api_url: str,
        process_file_func: Callable[[Dict[str, Any]], bool]
    ):
        """
        Args:
            db: Объект базы данных
            filewatcher_api_url: URL API FileWatcher для получения файлов
            process_file_func: Функция для обработки файла
        """
        self.db = db
        self.filewatcher_api_url = filewatcher_api_url
        self.process_file = process_file_func
        self.processed_count = 0
    
    def _get_next_file(self) -> Optional[Dict[str, Any]]:
        """Получить следующий файл из очереди filewatcher"""
        try:
            response = requests.get(f"{self.filewatcher_api_url}/api/next-file", timeout=5)
            if response.status_code == 204:
                return None  # Очередь пуста
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get next file from filewatcher: {e}")
            return None
    
    def start(self, poll_interval: int = 5, max_workers: int = 5):
        """Запустить worker с параллельной обработкой
        
        Args:
            poll_interval: Интервал опроса очереди в секундах
            max_workers: Максимальное количество файлов обрабатываемых параллельно
        """
        logger.info(f"Starting worker with {max_workers} max workers, poll interval {poll_interval}s")
        
        with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="worker") as executor:
            futures = {}  # future -> file_path mapping
            
            while True:
                try:
                    # Удаляем завершённые задачи и считаем успешные
                    done_futures = [f for f in list(futures.keys()) if f.done()]
                    for future in done_futures:
                        file_path = futures[future]
                        try:
                            success = future.result()
                            if success:
                                self.processed_count += 1
                                logger.info(f"📊 Total processed: {self.processed_count}")
                        except Exception as e:
                            logger.error(f"Task failed for {file_path}: {e}")
                        del futures[future]
                    
                    # Если есть свободные слоты, берём новые файлы
                    while len(futures) < max_workers:
                        file_info = self._get_next_file()
                        
                        if file_info is None:
                            # Очередь пуста
                            break
                        
                        # Помечаем файл как processed СРАЗУ, чтобы избежать дублирования
                        self.db.mark_as_processed(file_info['hash'])
                        
                        # Запускаем обработку в отдельном потоке
                        future = executor.submit(self.process_file, file_info)
                        futures[future] = file_info['path']
                        logger.info(f"🚀 Started: {file_info['path']} | Active: {len(futures)}/{max_workers}")
                    
                    # Если нет активных задач и очередь пуста, ждём
                    if not futures:
                        logger.debug("Queue is empty, waiting...")
                        time.sleep(poll_interval)
                    else:
                        # Есть активные задачи, проверяем чаще
                        time.sleep(0.2)
                        
                except KeyboardInterrupt:
                    logger.info("Shutting down worker...")
                    logger.info(f"Waiting for {len(futures)} active tasks to complete...")
                    # Ждём завершения активных задач
                    for future in as_completed(futures.keys()):
                        try:
                            future.result()
                        except Exception:
                            pass
                    break
                except Exception as e:
                    logger.error(f"Unexpected error in worker loop: {e}")
                    time.sleep(poll_interval)
        
        logger.info(f"Worker stopped. Total files processed: {self.processed_count}")
