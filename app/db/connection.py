"""
Подключение к PostgreSQL через asyncpg
"""

import asyncpg
from contextlib import asynccontextmanager
from typing import Optional
import logging

from settings import settings

logger = logging.getLogger(__name__)


class Database:
    """Менеджер подключений к PostgreSQL"""
    
    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None
    
    async def connect(self):
        """Создаёт connection pool"""
        if self.pool is not None:
            logger.warning("Database pool already exists")
            return
        
        try:
            self.pool = await asyncpg.create_pool(
                dsn=settings.DATABASE_URL,
                min_size=1,
                max_size=settings.DB_POOL_SIZE,
                max_inactive_connection_lifetime=300,
                command_timeout=60
            )
            logger.info("Database connection pool created")
            
            # Проверяем подключение
            async with self.pool.acquire() as conn:
                version = await conn.fetchval("SELECT version()")
                logger.info(f"Connected to PostgreSQL: {version}")
        
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}", exc_info=True)
            raise
    
    async def disconnect(self):
        """Закрывает connection pool"""
        if self.pool is None:
            return
        
        await self.pool.close()
        self.pool = None
        logger.info("Database connection pool closed")
    
    @asynccontextmanager
    async def acquire(self):
        """
        Context manager для получения подключения из pool
        
        Usage:
            async with db.acquire() as conn:
                result = await conn.fetch("SELECT ...")
        """
        if self.pool is None:
            raise RuntimeError("Database pool not initialized. Call connect() first.")
        
        async with self.pool.acquire() as connection:
            yield connection
    
    async def execute(self, query: str, *args):
        """Выполняет SQL запрос без возврата результата"""
        async with self.acquire() as conn:
            return await conn.execute(query, *args)
    
    async def fetch(self, query: str, *args):
        """Выполняет SQL запрос и возвращает все строки"""
        async with self.acquire() as conn:
            return await conn.fetch(query, *args)
    
    async def fetchrow(self, query: str, *args):
        """Выполняет SQL запрос и возвращает одну строку"""
        async with self.acquire() as conn:
            return await conn.fetchrow(query, *args)
    
    async def fetchval(self, query: str, *args):
        """Выполняет SQL запрос и возвращает одно значение"""
        async with self.acquire() as conn:
            return await conn.fetchval(query, *args)


# Глобальный экземпляр
db = Database()


async def init_db():
    """Инициализация БД при старте приложения"""
    await db.connect()
    await create_tables()


async def close_db():
    """Закрытие БД при остановке приложения"""
    await db.disconnect()


async def create_tables():
    """Создаёт таблицы если их нет"""
    async with db.acquire() as conn:
        # Включаем расширение pgvector
        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        
        # Таблица file_state
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS file_state (
                id SERIAL PRIMARY KEY,
                file_path TEXT NOT NULL UNIQUE,
                file_size BIGINT NOT NULL,
                file_hash TEXT,
                file_mtime DOUBLE PRECISION,
                status_sync TEXT DEFAULT 'ok',
                last_checked TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Индексы для file_state
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_file_path ON file_state(file_path)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_file_hash ON file_state(file_hash)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_status_sync ON file_state(status_sync)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_last_checked ON file_state(last_checked)")
        
        # Таблица documents (векторные чанки)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id BIGSERIAL PRIMARY KEY,
                file_hash TEXT NOT NULL,
                file_path TEXT NOT NULL,
                chunk_index INTEGER NOT NULL,
                chunk_text TEXT NOT NULL,
                embedding VECTOR(1024),
                metadata JSONB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                
                CONSTRAINT unique_chunk UNIQUE (file_hash, chunk_index)
            )
        """)
        
        # Индексы для documents
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_documents_file_hash ON documents(file_hash)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_documents_file_path ON documents(file_path)")
        
        # Векторный индекс (ivfflat для быстрого поиска)
        # Используем cosine distance для similarity search
        try:
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_documents_embedding 
                ON documents USING ivfflat (embedding vector_cosine_ops)
                WITH (lists = 100)
            """)
        except Exception as e:
            logger.warning(f"Could not create vector index (will work without it): {e}")
        
        logger.info("Database tables created/verified")


@asynccontextmanager
async def get_db():
    """
    Context manager для работы с БД
    
    Usage:
        async with get_db() as conn:
            result = await conn.fetch("SELECT ...")
    """
    async with db.acquire() as connection:
        yield connection
