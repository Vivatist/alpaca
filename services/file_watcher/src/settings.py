"""
Настройки File Watcher Service

ВАЖНО: Все значения настроек задаются в docker-compose.yml
Здесь только описание структуры без дефолтных значений
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class FileWatcherSettings(BaseSettings):
    """Настройки для File Watcher контейнера
    
    Все значения передаются через environment variables из docker-compose.yml
    """
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )
    
    # === CREDENTIALS ===
    DATABASE_URL: str  # PostgreSQL connection string (из .env)
    
    # === LOGGING ===
    LOG_LEVEL: str  # Уровень логирования: DEBUG, INFO, WARNING, ERROR
    LOG_FORMAT: str = "%(asctime)s | %(levelname)-8s | %(name)s - %(message)s"
    
    # === DATABASE ===
    FILES_TABLE_NAME: str  # Название таблицы для файлов
    
    # === FILE MONITORING ===
    MONITORED_PATH: str  # Путь к папке мониторинга (внутри контейнера)
    SCAN_INTERVAL_SECONDS: int  # Период сканирования в секундах
    
    # === FILE FILTER ===
    ALLOWED_EXTENSIONS: str  # Разрешённые расширения файлов (через запятую)
    FILE_MIN_SIZE: int  # Минимальный размер файла в байтах
    FILE_MAX_SIZE: int  # Максимальный размер файла в байтах
    EXCLUDED_DIRS: str  # Исключённые директории (через запятую)
    EXCLUDED_PATTERNS: str  # Исключённые паттерны файлов (через запятую)
    
    # === TESTING ===
    PRE_LAUNCH_TESTS: bool  # Запускать тесты перед стартом контейнера


settings = FileWatcherSettings()
