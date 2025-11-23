"""
Process Lock - защита от дублирования процессов
Аналог bind() для сокетов - гарантирует единственный экземпляр процесса
"""
import os
import sys
import atexit
import signal
from app.utils.logging import get_logger


logger = get_logger(__name__)


class ProcessLock:
    """Управление PID файлом для предотвращения дублирования процессов"""
    
    def __init__(self, pid_file: str = '/tmp/alpaca_rag.pid'):
        """
        Args:
            pid_file: Путь к PID файлу
        """
        self.pid_file = pid_file
        self._acquired = False
    
    def acquire(self):
        """
        Проверяет что процесс не запущен и создаёт PID файл.
        Выходит с ошибкой если процесс уже запущен.
        """
        if os.path.exists(self.pid_file):
            try:
                with open(self.pid_file, 'r') as f:
                    old_pid = int(f.read().strip())
                
                # Проверяем жив ли процесс
                try:
                    os.kill(old_pid, 0)  # Не убивает, просто проверяет существование
                    logger.error(f"❌ Process already running (PID: {old_pid})")
                    logger.error(f"   To stop: kill {old_pid}")
                    logger.error(f"   Or if it's dead: rm {self.pid_file}")
                    sys.exit(1)
                except OSError:
                    # Процесс мёртв, удаляем старый PID файл
                    logger.info(f"Removing stale PID file (process {old_pid} is dead)")
                    os.remove(self.pid_file)
            except (ValueError, IOError) as e:
                logger.warning(f"Invalid PID file, removing: {e}")
                os.remove(self.pid_file)
        
        # Записываем наш PID
        try:
            with open(self.pid_file, 'w') as f:
                f.write(str(os.getpid()))
            self._acquired = True
            logger.info(f"Acquired process lock (PID: {os.getpid()}, file: {self.pid_file})")
        except IOError as e:
            logger.error(f"Failed to create PID file: {e}")
            sys.exit(1)
    
    def release(self):
        """Удаляет PID файл при завершении"""
        if not self._acquired:
            return
        
        try:
            if os.path.exists(self.pid_file):
                os.remove(self.pid_file)
                logger.info("Released process lock")
                self._acquired = False
        except Exception as e:
            logger.error(f"Failed to release lock: {e}")
    
    def setup_handlers(self):
        """
        Регистрирует обработчики для автоматического освобождения lock при выходе.
        Вызывайте после acquire().
        """
        if not self._acquired:
            raise RuntimeError("Lock must be acquired before setting up handlers")
        
        # Регистрируем очистку при нормальном выходе
        atexit.register(self.release)
        
        # Регистрируем обработчики сигналов
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Обработчик сигналов для graceful shutdown"""
        logger.info(f"Received signal {signum}, shutting down...")
        self.release()
        sys.exit(0)
    
    def __enter__(self):
        """Context manager support"""
        self.acquire()
        self.setup_handlers()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager support"""
        self.release()
