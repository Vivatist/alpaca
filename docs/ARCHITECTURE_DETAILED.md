# Подробное описание архитектуры ALPACA

> **⚠️ УСТАРЕЛО**: Этот документ описывает старую архитектуру с domain facades и FileService.  
> **Актуальное описание:** См. `ARCHITECTURE_SIMPLE.md` (упрощённая архитектура после рефакторинга января 2025)

Этот документ сохранён для исторической справки и понимания эволюции проекта. Если вам нужно понять **текущую** архитектуру — читайте `ARCHITECTURE_SIMPLE.md`.

---

## ⚠️ Что изменилось (январь 2025)

После реализации Clean Architecture выполнено **радикальное упрощение**:

- ❌ **Удалены domain facades:** `set_chunker()`, `get_embedder()`, `configure_parser_registry()`
- ❌ **Удалён FileService:** логика перенесена в IngestDocument и repository
- ❌ **Упрощён bootstrap:** 8 функций → 1 функция (230 строк → 60 строк)
- ❌ **Упрощён WorkerApplication:** 10 полей → 2 поля (worker, repository)

**См. документацию:**
- `ARCHITECTURE_SIMPLE.md` — актуальная архитектура
- `REFACTORING_REPORT.md` — детальный отчёт об упрощении
- `architecture_roadmap.md` — история развития (этапы 1-6)

---

## Содержание (старая архитектура)

1. [Общая картина](#1-общая-картина)
2. [Внешние сервисы](#2-внешние-сервисы)
3. [Слой Domain (Домен)](#3-слой-domain-домен)
4. [Слой Application (Приложение)](#4-слой-application-приложение)
5. [Слой Infrastructure (Инфраструктура)](#5-слой-infrastructure-инфраструктура)
6. [Utils (Утилиты)](#6-utils-утилиты)
7. [Bootstrap и Dependency Injection](#7-bootstrap-и-dependency-injection) ⚠️ УСТАРЕЛО
8. [Процесс обработки файла](#8-процесс-обработки-файла)
9. [Как добавить новую фичу](#9-как-добавить-новую-фичу)
10. [Почему именно так](#10-почему-именно-так)

---

## 1. Общая картина

ALPACA — это RAG-система (Retrieval Augmented Generation) для обработки документов. Она:

1. Следит за папкой `monitored_folder`
2. Парсит документы (DOCX, PDF, PPTX, XLS, TXT)
3. Разбивает на чанки
4. Создаёт векторные представления (embeddings)
5. Сохраняет в PostgreSQL с pgvector для поиска

### Высокоуровневая схема

```
┌─────────────────┐
│ monitored_folder│
└────────┬────────┘
         │
         ▼
┌─────────────────┐      ┌──────────────┐
│  FileWatcher    │─────▶│ PostgreSQL   │
│  (Docker)       │      │ + pgvector   │
└────────┬────────┘      └──────┬───────┘
         │                      ▲
         │ REST API             │
         ▼                      │
┌─────────────────┐             │
│  Worker         │─────────────┘
│  (Python)       │
└────────┬────────┘
         │
         ├──────────▶ Ollama (LLM + embeddings)
         └──────────▶ Unstructured (парсинг)
```

### Основные компоненты

- **FileWatcher** — Docker-сервис, сканирует папку, обновляет статусы в БД
- **Worker** — Python-процесс, берёт файлы из очереди и обрабатывает
- **Ollama** — локальная LLM (qwen2.5:32b) и модель эмбеддингов (bge-m3)
- **Unstructured** — API для парсинга сложных документов
- **PostgreSQL** — база с расширением pgvector

---

## 2. Внешние сервисы

### 2.1 Supabase (PostgreSQL + pgvector)

**Что это:** Self-hosted Supabase с PostgreSQL 15 и расширением pgvector.

**Где живёт:** `~/supabase/docker` (отдельная установка)

**Порты:**
- PostgreSQL: `54322` (не стандартный 5432!)
- Dashboard: `8000`

**Таблицы:**

```sql
-- files: отслеживание файлов
CREATE TABLE files (
    hash VARCHAR PRIMARY KEY,
    path VARCHAR NOT NULL,
    size BIGINT,
    mtime FLOAT,
    status_sync VARCHAR,  -- added/updated/deleted/processed/ok/error
    last_checked TIMESTAMP
);

-- chunks: векторное хранилище
CREATE TABLE chunks (
    id BIGSERIAL PRIMARY KEY,
    content TEXT,
    metadata JSONB,  -- {file_hash, file_path, chunk_index, total_chunks}
    embedding VECTOR(1024)  -- для модели bge-m3
);
```

**Почему Supabase?**
- Быстрое развёртывание PostgreSQL + pgvector
- Dashboard для мониторинга
- REST API (пока не используется, но может пригодиться)

**Альтернативы:**
- Чистый PostgreSQL + установка pgvector вручную (сложнее)
- Managed решение типа Neon.tech (дороже, зависимость от облака)

### 2.2 FileWatcher

**Что это:** Docker-сервис на Node.js, сканирует `monitored_folder`.

**Что делает:**
1. Каждые N секунд сканирует папку
2. Вычисляет SHA256 для новых/изменённых файлов
3. Обновляет таблицу `files` с правильным `status_sync`
4. Предоставляет REST API для получения очереди

**API:**
```bash
GET /api/next-file  # Возвращает файл для обработки
GET /api/queue/stats  # Статистика очереди
```

**Приоритеты обработки:**
1. `deleted` (удалённые файлы — нужно удалить чанки)
2. `updated` (изменённые — переобработать)
3. `added` (новые)

**Почему отдельный сервис?**
- Лёгкая горизонтальная масштабируемость (можно запустить несколько Worker'ов)
- Отделение мониторинга ФС от обработки
- Можно перезапускать Worker без потери состояния

### 2.3 Ollama

**Что это:** Локальная LLM платформа с поддержкой GPU.

**Модели:**
- `qwen2.5:32b` — основная LLM (32 млрд параметров)
- `bge-m3` — модель эмбеддингов (1024 размерность)

**API для эмбеддингов:**
```python
response = requests.post(
    "http://localhost:11434/api/embeddings",
    json={"model": "bge-m3", "prompt": text}
)
embedding = response.json()['embedding']  # list[float] из 1024 элементов
```

**Почему Ollama?**
- Работает локально (приватность данных)
- Поддержка GPU (быстрые эмбеддинги)
- Простой API
- Модели хранятся локально

**Альтернативы:**
- OpenAI API (платно, зависимость от облака)
- HuggingFace Transformers (сложнее управление моделями)

### 2.4 Unstructured

**Что это:** API для парсинга документов с OCR.

**Используется для:**
- PDF с изображениями
- Сложные PPTX
- Fallback для проблемных документов

**Пример запроса:**
```python
with open(file_path, 'rb') as f:
    response = requests.post(
        "http://localhost:9000/general/v0/general",
        files={'files': (filename, f)},
        data={'strategy': 'hi_res', 'languages': 'rus,eng'}
    )
```

**Почему используется выборочно?**
- Медленнее чем нативные парсеры
- Для простых DOCX достаточно python-docx
- Для PDF с текстом достаточно PyMuPDF

---

## 3. Слой Domain (Домен)

**Местоположение:** `core/domain/`

**Принцип:** Домен описывает **что умеет делать** система, но не **как именно**.

### 3.1 Модели данных (`core/domain/files/models.py`)

**FileSnapshot** — основная сущность:

```python
@dataclass(slots=True)
class FileSnapshot:
    path: str           # Относительный путь от monitored_folder
    hash: str           # SHA256
    status_sync: str    # added/updated/deleted/processed/ok/error
    size: Optional[int] = None
    raw_text: Optional[str] = None  # Распарсенный текст
    mtime: Optional[float] = None
    last_checked: Optional[datetime] = None
    
    @property
    def full_path(self) -> str:
        """Абсолютный путь до файла."""
        return os.path.join(settings.MONITORED_PATH, self.path)
```

**Почему dataclass?**
- Иммутабельность (slots=True)
- Автоматическая генерация `__init__`, `__repr__`
- Типизация из коробки

**Жизненный цикл статусов:**
```
added/updated/deleted  →  processed  →  ok/error
      ↑                                    ↓
      └─────────── (retry) ────────────────┘
```

### 3.2 Репозиторий (`core/domain/files/repository.py`)

**Database** — протокол (интерфейс):

```python
class Database(Protocol):
    def get_connection(self) -> ContextManager[Connection]: ...
    def mark_as_ok(self, file: FileSnapshot) -> None: ...
    def mark_as_error(self, file: FileSnapshot) -> None: ...
    # ... другие методы
```

**Почему Protocol?**
- Домен не знает о PostgreSQL
- Легко подменить в тестах
- Соответствует принципу Dependency Inversion

### 3.3 Фасады обработки документов ⚠️ УСТАРЕЛО

> **В текущей версии:** Domain facades удалены. Теперь используются только type aliases.

**Местоположение (старая версия):** `core/domain/document_processing/`

~~Домен предоставлял точки расширения через глобальные функции~~:

```python
# ❌ УДАЛЕНО в январе 2025
configure_parser_registry(registry: ParserRegistry) -> None
get_parser_for_path(file_path: str) -> Optional[ParserProtocol]
set_chunker(chunker: Chunker) -> None
set_embedder(embedder: Embedder) -> None
```

**Текущая версия (упрощённая):**

Domain экспортирует только **type aliases**:

```python
# core/domain/document_processing/chunkers/__init__.py
Chunker = Callable[[FileSnapshot], List[str]]

# core/domain/document_processing/embedders/__init__.py
Embedder = Callable[[FileRepository, FileSnapshot, List[str]], int]
```

Зависимости теперь передаются через **конструкторы** (Dependency Injection):

```python
@dataclass
class IngestDocument:
    parser_registry: ParserRegistry  # ← явная зависимость
    chunker: Chunker                 # ← явная зависимость
    embedder: Embedder               # ← явная зависимость
```

**Почему изменили:**
- Глобальное состояние усложняло понимание кода
- Неявные зависимости через `set_*()` / `get_*()`
- Сложно отследить, где и когда настраиваются компоненты

**Альтернативы (которые рассматривались):**
- ~~Service Locator~~ — ещё хуже, скрывает зависимости
- ✅ **Explicit DI** — выбрано, явные зависимости через конструкторы

---

## 4. Слой Application (Приложение)

**Местоположение:** `core/application/`

**Принцип:** Application реализует **как именно** работают use-case'ы и бизнес-логика.

### 4.1 Use Cases (`core/application/processing/use_cases.py`)

#### IngestDocument

**Что делает:** Полный пайплайн обработки файла.

**Структура:**

```python
@dataclass
class IngestDocument:
    file_service: FileService
    database: Database
    parser_resolver: ParserResolver  # функция: str -> Parser
    chunker: Chunker                 # функция: FileSnapshot -> List[str]
    embedder: Embedder               # функция: (db, file, chunks) -> int
    parse_semaphore: Semaphore       # ограничение параллельности
    embed_semaphore: Semaphore
    
    def __call__(self, file: FileSnapshot) -> bool:
        # 1. Выбрать парсер
        parser = self.parser_resolver(file.path)
        
        # 2. Парсинг (с семафором)
        with self.parse_semaphore:
            file.raw_text = parser.parse(file)
        
        # 3. Чанкинг
        chunks = self.chunker(file)
        
        # 4. Эмбеддинг (с семафором)
        with self.embed_semaphore:
            count = self.embedder(self.database, file, chunks)
        
        # 5. Обновить статус
        self.file_service.mark_as_ok(file)
        return True
```

**Почему семафоры?**
- Ограничиваем параллельный парсинг (CPU-bound)
- Ограничиваем параллельные запросы к Ollama (GPU memory)
- Настройки: `WORKER_MAX_CONCURRENT_PARSING`, `WORKER_MAX_CONCURRENT_EMBEDDING`

**Пример настройки:**

```python
# settings.py
WORKER_MAX_CONCURRENT_PARSING = 2   # Макс 2 файла парсятся одновременно
WORKER_MAX_CONCURRENT_EMBEDDING = 3 # Макс 3 запроса к Ollama
```

#### ProcessFileEvent

**Что делает:** Обрабатывает события от FileWatcher.

```python
@dataclass
class ProcessFileEvent:
    ingest_document: IngestDocument
    file_service: FileService
    
    def __call__(self, file_info: Dict[str, Any]) -> bool:
        file = FileSnapshot(**file_info)
        
        if file.status_sync == "deleted":
            # Удалить файл и чанки из БД
            self.file_service.delete_file_and_chunks(file)
            return True
        
        if file.status_sync == "updated":
            # Удалить старые чанки, запустить пайплайн
            self.file_service.delete_chunks_only(file)
            return self.ingest_document(file)
        
        if file.status_sync == "added":
            # Просто запустить пайплайн
            return self.ingest_document(file)
```

**Почему отдельный use-case?**
- Разделение ответственности (обработка событий vs пайплайн)
- Легко тестировать каждую ветку отдельно
- Можно добавить новые статусы без изменения пайплайна

### 4.2 Сервисы ~~(`core/application/files/services.py`)~~ ⚠️ УДАЛЕНО

> **В текущей версии:** FileService удалён. Логика распределена между IngestDocument и прямыми вызовами repository.

**FileService (старая версия)** — тонкая обёртка над repository:

```python
# ❌ УДАЛЕНО в январе 2025
class FileService:
    def __init__(self, repository: Database):
        self.db = repository
    
    def mark_as_ok(self, file: FileSnapshot) -> None:
        self.db.mark_as_ok(file)  # Просто делегирование
    
    def delete_chunks_only(self, file: FileSnapshot) -> None:
        self.db.delete_chunks_by_hash(file.hash)  # Просто делегирование
```

**Проблема:** FileService был тонкой обёрткой без бизнес-логики. Все методы просто делегировали вызовы в repository.

**Текущая версия (упрощённая):**

Логика распределена:

1. **Сохранение на диск** → перенесено в `IngestDocument._save_to_disk()`
2. **Операции с БД** → прямые вызовы `repository.mark_as_ok()`, `repository.delete_chunks_by_hash()`

```python
@dataclass
class IngestDocument:
    repository: FileRepository  # ← напрямую, без FileService
    
    def _save_to_disk(self, file: FileSnapshot) -> None:
        """Сохранить raw_text для отладки."""
        if not file.raw_text:
            return
        temp_dir = Path(settings.TMP_MD_PATH)
        temp_dir.mkdir(exist_ok=True)
        (temp_dir / f"{file.path}.md").write_text(file.raw_text)
```

**Почему удалили:**
- Лишний слой абстракции без выгоды
- Нарушал Single Responsibility (смешивал БД и ФС операции)
- Усложнял понимание потока данных

### 4.3 Парсеры (`core/application/document_processing/parsers/`)

Каждый формат — отдельный парсер.

#### WordParser (`word/word_parser.py`)

**Стек технологий:**
- MarkItDown (базовая конвертация)
- python-docx (глубокий разбор)
- pytesseract (OCR для изображений)

**Процесс:**

```python
class WordParser(BaseParser):
    def __init__(self, enable_ocr: bool = True):
        super().__init__("word")
        self.enable_ocr = enable_ocr
    
    def _parse(self, file: FileSnapshot) -> str:
        # 1. Быстрая конвертация через MarkItDown
        md_text = markitdown.convert(file.full_path)
        
        # 2. Глубокий разбор через python-docx
        doc = Document(file.full_path)
        
        # 3. Извлечь текст из параграфов
        content = []
        for para in doc.paragraphs:
            if para.text.strip():
                content.append(para.text)
        
        # 4. Извлечь текст из таблиц
        for table in doc.tables:
            table_text = self._extract_table_text(table)
            content.append(table_text)
        
        # 5. OCR для изображений (если включено)
        if self.enable_ocr:
            for rel in doc.part.rels.values():
                if "image" in rel.target_ref:
                    image = rel.target_part.blob
                    ocr_text = self._ocr_image(image)
                    content.append(ocr_text)
        
        return "\n\n".join(content)
```

**Почему несколько библиотек?**
- MarkItDown быстрый, но неполный
- python-docx даёт доступ к структуре (таблицы, изображения)
- Tesseract для OCR (если в документе есть скриншоты с текстом)

#### PDFParser (`pdf/pdf_parser.py`)

**Стек:**
- PyMuPDF (fitz) — основной парсинг
- Unstructured API — fallback для сложных PDF

**Логика:**

```python
def _parse(self, file: FileSnapshot) -> str:
    try:
        # Пробуем PyMuPDF
        doc = fitz.open(file.full_path)
        text = []
        
        for page in doc:
            page_text = page.get_text()
            if page_text.strip():
                text.append(page_text)
        
        result = "\n\n".join(text)
        
        # Если текста мало — попробовать Unstructured
        if len(result) < 100:
            return self._fallback_to_unstructured(file)
        
        return result
    except Exception:
        return self._fallback_to_unstructured(file)
```

**Почему fallback?**
- PDF может содержать только изображения (scan)
- PyMuPDF не умеет OCR
- Unstructured медленный, но умеет OCR

#### Другие парсеры

- **PowerPointParser** — python-pptx + fallback Unstructured
- **ExcelParser** — openpyxl, автоопределение шапок
- **TXTParser** — определение кодировки (chardet)

### 4.4 Чанкеры (`core/application/document_processing/chunking/`)

**Текущая реализация** — простой fixed-size чанкинг:

```python
def chunking(file: FileSnapshot, chunk_size: int = 1000) -> List[str]:
    """Разбивает raw_text на чанки по chunk_size символов."""
    if not file.raw_text:
        return []
    
    text = file.raw_text
    chunks = []
    
    for i in range(0, len(text), chunk_size):
        chunk = text[i:i + chunk_size]
        if chunk.strip():
            chunks.append(chunk)
    
    return chunks
```

**Почему так просто?**
- Начальная реализация
- Работает для большинства документов
- Легко понять и отладить

**Альтернативы (TODO):**
- Семантический чанкинг (разбивка по параграфам/разделам)
- Рекурсивный чанкинг (LangChain)
- Чанкинг с перекрытием (overlap)

**Как добавить новый чанкер:**

```python
# 1. Создать функцию
def semantic_chunker(file: FileSnapshot) -> List[str]:
    # Разбить по параграфам
    return file.raw_text.split("\n\n")

# 2. В bootstrap передать новую функцию
chunker = semantic_chunker  # вместо default_chunker_impl
set_chunker(chunker)
```

### 4.5 Эмбеддеры (`core/application/document_processing/embedding/`)

#### custom_embedding (Ollama)

```python
def custom_embedding(db: Database, file: FileSnapshot, chunks: List[str]) -> int:
    """Создаёт эмбеддинги через Ollama и сохраняет в БД."""
    
    with db.get_connection() as conn:
        with conn.cursor() as cur:
            inserted_count = 0
            
            for idx, chunk_text in enumerate(chunks):
                # Запрос к Ollama
                response = requests.post(
                    f"{settings.OLLAMA_BASE_URL}/api/embeddings",
                    json={"model": settings.OLLAMA_EMBEDDING_MODEL, "prompt": chunk_text}
                )
                
                embedding = response.json()['embedding']
                embedding_str = '[' + ','.join(map(str, embedding)) + ']'
                
                # Метаданные
                metadata = {
                    'file_hash': file.hash,
                    'file_path': file.path,
                    'chunk_index': idx,
                    'total_chunks': len(chunks)
                }
                
                # Вставка в БД
                cur.execute("""
                    INSERT INTO chunks (content, metadata, embedding)
                    VALUES (%s, %s, %s::vector)
                """, (chunk_text, psycopg2.extras.Json(metadata), embedding_str))
                
                inserted_count += 1
            
            conn.commit()
    
    return inserted_count
```

**Почему HTTP запросы?**
- Ollama работает как отдельный сервис
- Можно масштабировать (несколько Worker → один Ollama)
- Простой API

#### langchain_embedding

Альтернативная реализация через LangChain:

```python
def langchain_embedding(db: Database, file: FileSnapshot, chunks: List[str]) -> int:
    """Использует LangChain OpenAI embeddings."""
    
    from langchain.embeddings import OpenAIEmbeddings
    
    embeddings_model = OpenAIEmbeddings()
    vectors = embeddings_model.embed_documents(chunks)
    
    # Сохранить в БД
    # ... аналогично custom_embedding
```

**Переключение:**

```bash
export EMBEDDER_BACKEND=langchain
python main.py
```

**Почему две реализации?**
- Ollama — бесплатно, локально, приватность
- LangChain/OpenAI — лучшее качество (но платно)
- Возможность A/B тестирования

---

## 5. Слой Infrastructure (Инфраструктура)

**Местоположение:** `core/infrastructure/`

**Принцип:** Адаптеры к внешним системам (БД, API, файловая система).

### 5.1 PostgresFileRepository

**Реализует:** Protocol `Database` из домена.

**Ключевые методы:**

```python
class PostgresFileRepository:
    def __init__(self, database_url: str, files_table: str = "files"):
        self.database_url = database_url
        self.files_table = files_table
    
    def get_connection(self) -> ContextManager[Connection]:
        """Возвращает connection с auto-commit/rollback."""
        return psycopg2.connect(self.database_url)
    
    def mark_as_ok(self, file: FileSnapshot) -> None:
        """UPDATE files SET status_sync='ok' WHERE hash=..."""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"UPDATE {self.files_table} SET status_sync='ok' WHERE hash=%s",
                    (file.hash,)
                )
            conn.commit()
    
    def delete_chunks_by_hash(self, file_hash: str) -> None:
        """DELETE FROM chunks WHERE metadata->>'file_hash'=..."""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM chunks WHERE metadata->>'file_hash' = %s",
                    (file_hash,)
                )
            conn.commit()
```

**Почему Context Manager?**
- Автоматический commit при успехе
- Автоматический rollback при исключении
- Нет забытых транзакций

**Пример:**

```python
with db.get_connection() as conn:
    with conn.cursor() as cur:
        cur.execute("INSERT INTO files ...")
        # Если здесь exception → автоматический rollback
        cur.execute("INSERT INTO chunks ...")
    # Здесь автоматический commit
```

**Альтернативы:**
- ORM (SQLAlchemy) — избыточно для простых запросов
- Asyncio (asyncpg) — не нужно (CPU-bound операции доминируют)

---

## 6. Utils (Утилиты)

**Местоположение:** `utils/`

### 6.1 Логирование (`utils/logging.py`)

**Настройка:**

```python
def setup_logging():
    """Настраивает логирование для всего приложения."""
    logging.basicConfig(
        level=settings.LOG_LEVEL,
        format=settings.LOG_FORMAT,
        handlers=[logging.StreamHandler()]
    )

def get_logger(name: str) -> logging.Logger:
    """Возвращает настроенный logger."""
    return logging.getLogger(name)
```

**Использование:**

```python
from utils.logging import get_logger

logger = get_logger("core.parser")
logger.info(f"✅ Parsed {len(text)} chars")
logger.error(f"❌ Failed to parse: {error}")
```

**Эмодзи-префиксы:**
- 🍎 — начало операции
- ✅ — успех
- ❌ — ошибка
- 📖 — парсинг
- 🔪 — чанкинг
- 🔮 — эмбеддинг

**Почему эмодзи?**
- Визуальное сканирование логов
- Быстро найти ошибки
- Удобство при отладке

### 6.2 Worker (`utils/worker.py`)

**Что делает:** Управляет пулом потоков и опрашивает FileWatcher.

```python
class Worker:
    def __init__(
        self,
        db: Database,
        filewatcher_api_url: str,
        process_file_func: Callable
    ):
        self.db = db
        self.api_url = filewatcher_api_url
        self.process_file = process_file_func
    
    def start(self, poll_interval: int, max_workers: int):
        """Запускает бесконечный цикл обработки."""
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            while True:
                # 1. Запросить файл из очереди
                response = requests.get(f"{self.api_url}/api/next-file")
                
                if response.status_code == 204:
                    # Очередь пуста
                    time.sleep(poll_interval)
                    continue
                
                file_info = response.json()
                
                # 2. Сразу пометить как processed (защита от дублей)
                self.db.mark_as_processed(file_info['hash'])
                
                # 3. Отправить в пул потоков
                executor.submit(self.process_file, file_info)
```

**Почему ThreadPoolExecutor?**
- Простота
- Ограничение параллельности (max_workers)
- GIL не проблема (IO-bound и семафоры контролируют CPU-bound)

**Альтернативы:**
- ProcessPoolExecutor (избыточно, сложнее передача состояния)
- Asyncio (не даёт преимуществ для CPU-bound парсинга)
- Celery (overkill для одного worker'а)

---

## 7. Bootstrap и Dependency Injection ⚠️ ИЗМЕНЕНО

> **В текущей версии:** Bootstrap упрощён с 230 строк (8 функций) до 60 строк (1 функция).

**Местоположение:** `core/application/bootstrap.py`

**Задача:** Собрать все зависимости в одном месте.

### 7.1 Структура WorkerApplication (текущая — упрощённая)

```python
@dataclass
class WorkerApplication:
    """Контейнер зависимостей worker'а."""
    worker: Worker           # Единственный публичный API
    repository: FileRepository  # Для тестов и сброса статусов
```

**Старая версия (10 полей):**

```python
# ❌ УСТАРЕЛО — было слишком много экспозиции
@dataclass
class WorkerApplication:
    settings: Settings
    repository: PostgresFileRepository
    file_service: FileService         # ← удалён
    parser_resolver: ParserResolver   # ← скрыт внутри
    ingest_document: IngestDocument   # ← скрыт внутри
    process_file_event: ProcessFileEvent  # ← скрыт внутри
    worker: Worker
    word_parser: WordParser           # ← скрыт внутри
    chunker: Chunker                  # ← скрыт внутри
    embedder: Embedder                # ← скрыт внутри
```

**Почему упростили:**
- Большинство полей не использовались извне
- Тесты обращались к внутренним компонентам (нарушение инкапсуляции)
- Worker — единственный нужный публичный API

### 7.2 Фабричные функции

```python
def build_repository(app_settings: Settings) -> PostgresFileRepository:
    """Создаёт репозиторий с учётом настроек."""
    return PostgresFileRepository(
        database_url=app_settings.DATABASE_URL,
        files_table=getattr(app_settings, "FILES_TABLE_NAME", "files"),
    )

def build_word_parser() -> WordParser:
    """Создаёт Word-парсер с OCR."""
    return WordParser(enable_ocr=True)

def build_chunker() -> Chunker:
    """Создаёт чанкер (можно параметризировать)."""
    return default_chunker_impl

def _resolve_embedder(app_settings: Settings) -> Embedder:
    """Выбирает embedder на основе настроек."""
    backend = getattr(app_settings, "EMBEDDER_BACKEND", None)
    
    if backend == "custom" or backend is None:
        return custom_embedding
    elif backend == "langchain":
        return langchain_embedding
    else:
        raise ValueError(f"Unknown EMBEDDER_BACKEND: {backend}")
```

### 7.3 Главная фабрика (текущая — упрощённая)

```python
def build_worker_application(app_settings: Settings = settings) -> WorkerApplication:
    """Собирает все зависимости (упрощённая версия)."""
    
    # 1. Infrastructure
    repository = PostgresFileRepository(
        database_url=app_settings.DATABASE_URL,
        files_table=getattr(app_settings, "FILES_TABLE_NAME", "files"),
    )
    
    # 2. Parsers (создаём экземпляры напрямую)
    word_parser = WordParser(...)
    pdf_parser = PDFParser(...)
    ppt_parser = PowerPointParser(...)
    excel_parser = ExcelParser(...)
    txt_parser = TXTParser()
    
    # 3. ParserRegistry (прямые экземпляры, не фабрики)
    parser_registry = ParserRegistry(parsers={
        (".doc", ".docx"): word_parser,
        (".pdf",): pdf_parser,
        (".ppt", ".pptx"): ppt_parser,
        (".xls", ".xlsx"): excel_parser,
        (".txt",): txt_parser,
    })
    
    # 4. Chunker и Embedder
    chunker = chunk_document  # Функция напрямую
    embedder = custom_embedding if not app_settings.EMBEDDER_BACKEND 
               else langchain_embedding
    
    # 5. Use-cases
    ingest_document = IngestDocument(
        repository=repository,        # ← напрямую, без FileService
        parser_registry=parser_registry,
        chunker=chunker,
        embedder=embedder,
        parse_semaphore=Semaphore(app_settings.WORKER_MAX_CONCURRENT_PARSING),
        embed_semaphore=Semaphore(app_settings.WORKER_MAX_CONCURRENT_EMBEDDING),
    )
    
    process_file_event = ProcessFileEvent(
        ingest_document=ingest_document,
        repository=repository  # ← напрямую
    )
    
    # 6. Worker
    worker = Worker(
        db=repository,
        filewatcher_api_url=f"http://{app_settings.FILEWATCHER_HOST}:{app_settings.FILEWATCHER_PORT}",
        process_file_func=process_file_event,
    )
    
    # 7. Вернуть упрощённый контейнер (только 2 поля)
    return WorkerApplication(worker=worker, repository=repository)
```

**Изменения:**
- ❌ Удалено 8 отдельных `build_*` функций
- ❌ Удалена настройка domain facades (`configure_parser_registry`, `set_chunker`)
- ✅ Всё создаётся inline в одной функции
- ✅ Явные зависимости через конструкторы
- ✅ 60 строк вместо 230

### 7.4 ~~Настройка доменного фасада~~ ⚠️ УДАЛЕНО

```python
# ❌ УДАЛЕНО в январе 2025
def _configure_document_processing_facade(...) -> None:
    configure_parser_registry(registry)  # ← глобальное состояние
    set_chunker(chunker)                 # ← глобальное состояние
    set_embedder(embedder)               # ← глобальное состояние
```

**Проблема:** Глобальное состояние скрывало зависимости и усложняло тестирование.

**Текущая версия:** Зависимости передаются через конструкторы, никакой глобальной настройки не требуется.

```python
# ✅ Текущий подход
ingest_document = IngestDocument(
    parser_registry=parser_registry,  # ← явная зависимость
    chunker=chunker,                  # ← явная зависимость
    embedder=embedder                 # ← явная зависимость
)
```

### 7.5 Использование в main.py (актуально)

```python
from core.application.bootstrap import build_worker_application
from utils.logging import setup_logging

if __name__ == "__main__":
    setup_logging()
    
    # Собрать все зависимости
    app = build_worker_application(settings)
    
    # Сбросить зависшие файлы
    app.repository.reset_processed_statuses()
    
    # Запустить worker
    app.worker.start(
        poll_interval=settings.WORKER_POLL_INTERVAL,
        max_workers=settings.WORKER_MAX_CONCURRENT_FILES,
    )
```

**Преимущества упрощённой версии:**
- ✅ Одна функция вместо восьми
- ✅ Явные зависимости (нет глобального состояния)
- ✅ Простота понимания (60 строк кода)
- ✅ Легко тестировать (передать моки в конструкторы)

---

## 8. Процесс обработки файла

Рассмотрим полный путь от появления файла до сохранения в БД.

### 8.1 Шаг 1: Мониторинг файлов

```
1. Пользователь кладёт файл в monitored_folder/
2. FileWatcher (Docker) замечает новый файл
3. Вычисляет SHA256
4. Вставляет в БД: INSERT INTO files (..., status_sync='added')
```

### 8.2 Шаг 2: Получение файла Worker'ом

```python
# Worker делает запрос
response = requests.get("http://localhost:8081/api/next-file")

# FileWatcher возвращает:
{
    "path": "docs/report.docx",
    "hash": "abc123...",
    "status_sync": "added",
    "size": 102400
}

# Worker сразу помечает как processed
db.mark_as_processed(file['hash'])
```

**Почему сразу processed?**
- Защита от параллельной обработки (если несколько Worker'ов)
- FileWatcher больше не вернёт этот файл

### 8.3 Шаг 3: Выбор обработчика

```python
# ProcessFileEvent решает что делать
file = FileSnapshot(**file_info)

if file.status_sync == "added":
    return ingest_document(file)  # Полный пайплайн
elif file.status_sync == "updated":
    file_service.delete_chunks_only(file)  # Удалить старые чанки
    return ingest_document(file)           # Переобработать
elif file.status_sync == "deleted":
    file_service.delete_file_and_chunks(file)  # Удалить всё
    return True
```

### 8.4 Шаг 4: Парсинг документа

```python
# IngestDocument выбирает парсер
parser = parser_resolver(file.path)  # WordParser для .docx

# Парсинг с семафором (ограничение параллельности)
with parse_semaphore:
    file.raw_text = parser.parse(file)

# Пример для DOCX:
# 1. MarkItDown — быстрая конвертация
# 2. python-docx — извлечение текста из параграфов и таблиц
# 3. pytesseract — OCR для изображений (если enable_ocr=True)

# Результат: file.raw_text = "# Заголовок\n\nТекст документа..."
```

### 8.5 Шаг 5: Сохранение на диск

```python
# FileService сохраняет для отладки
file_service.save_file_to_disk(file)

# Создаётся: /home/alpaca/tmp_md/docs/report.docx.md
# Содержимое: raw_text в Markdown формате
```

### 8.6 Шаг 6: Чанкинг

```python
# Разбить текст на чанки
chunks = chunker(file)

# Пример (fixed-size chunker):
# Входит: "Очень длинный текст документа..." (5000 символов)
# Выходит: ["Очень длинный...", "...текст докум...", "...ента."] (5 чанков по 1000 символов)
```

### 8.7 Шаг 7: Создание эмбеддингов

```python
# Эмбеддинг с семафором (ограничение GPU)
with embed_semaphore:
    count = embedder(database, file, chunks)

# Внутри embedder:
for idx, chunk_text in enumerate(chunks):
    # 1. Запрос к Ollama
    response = requests.post(
        "http://localhost:11434/api/embeddings",
        json={"model": "bge-m3", "prompt": chunk_text}
    )
    embedding = response.json()['embedding']  # [0.123, -0.456, ...] (1024 числа)
    
    # 2. Сохранить в БД
    cur.execute("""
        INSERT INTO chunks (content, metadata, embedding)
        VALUES (%s, %s, %s::vector)
    """, (chunk_text, json_metadata, embedding_string))
```

### 8.8 Шаг 8: Обновление статуса

```python
# Пометить файл как успешно обработанный
file_service.mark_as_ok(file)

# UPDATE files SET status_sync='ok' WHERE hash='abc123...'
```

### 8.9 Финальное состояние БД

**Таблица `files`:**
```
| hash    | path              | status_sync | last_checked        |
|---------|-------------------|-------------|---------------------|
| abc123  | docs/report.docx  | ok          | 2025-11-30 12:34:56 |
```

**Таблица `chunks`:**
```
| id | content          | metadata                                        | embedding      |
|----|------------------|-------------------------------------------------|----------------|
| 1  | "Очень длинный..." | {"file_hash":"abc123", "chunk_index":0, ...}   | [0.123, ...]   |
| 2  | "...текст докум..." | {"file_hash":"abc123", "chunk_index":1, ...}   | [-0.456, ...]  |
```

---

## 9. Как добавить новую фичу

### 9.1 Добавить поддержку нового формата (например, RTF)

**Шаг 1:** Создать парсер в `core/application/document_processing/parsers/rtf/`

```python
# rtf_parser.py
from ..base_parser import BaseParser

class RTFParser(BaseParser):
    def __init__(self):
        super().__init__("rtf")
    
    def _parse(self, file: FileSnapshot) -> str:
        # Логика парсинга RTF
        # Можно использовать библиотеку striprtf
        from striprtf.striprtf import rtf_to_text
        
        with open(file.full_path, 'r') as f:
            rtf_content = f.read()
        
        return rtf_to_text(rtf_content)
```

**Шаг 2:** Экспортировать из `parsers/__init__.py`

```python
from .rtf.rtf_parser import RTFParser

__all__ = [..., "RTFParser"]
```

**Шаг 3:** Добавить в bootstrap

```python
def _build_parser_registry(word_parser: WordParser) -> ParserRegistry:
    return ParserRegistry(
        registry=(
            (DOC_EXTENSIONS, _reuse(word_parser)),
            ((".pdf",), PDFParser),
            ((".rtf",), RTFParser),  # ← Новая строка
            # ...
        ),
    )
```

**Готово!** Теперь RTF-файлы будут обрабатываться автоматически.

### 9.2 Добавить семантический чанкинг

**Шаг 1:** Создать новый чанкер

```python
# core/application/document_processing/chunking/semantic_chunker.py

def semantic_chunking(file: FileSnapshot) -> List[str]:
    """Разбивает текст по семантическим границам."""
    
    if not file.raw_text:
        return []
    
    # Разбить по двойным переносам (параграфы)
    paragraphs = file.raw_text.split("\n\n")
    
    # Объединить короткие параграфы
    chunks = []
    current_chunk = ""
    
    for para in paragraphs:
        if len(current_chunk) + len(para) > 1000:
            if current_chunk:
                chunks.append(current_chunk)
            current_chunk = para
        else:
            current_chunk += "\n\n" + para
    
    if current_chunk:
        chunks.append(current_chunk)
    
    return chunks
```

**Шаг 2:** Добавить выбор в bootstrap

```python
def build_chunker(app_settings: Settings) -> Chunker:
    chunker_type = getattr(app_settings, "CHUNKER_TYPE", "fixed")
    
    if chunker_type == "semantic":
        from core.application.document_processing.chunking import semantic_chunking
        return semantic_chunking
    else:
        return default_chunker_impl
```

**Шаг 3:** Добавить настройку

```python
# settings.py
CHUNKER_TYPE: str = "semantic"  # или "fixed"
```

**Использование:**

```bash
export CHUNKER_TYPE=semantic
python main.py
```

### 9.3 Добавить кэширование эмбеддингов

**Идея:** Не пересчитывать эмбеддинг для одинаковых чанков.

**Шаг 1:** Добавить таблицу кэша

```sql
CREATE TABLE embedding_cache (
    text_hash VARCHAR PRIMARY KEY,
    embedding VECTOR(1024),
    created_at TIMESTAMP DEFAULT NOW()
);
```

**Шаг 2:** Модифицировать embedder

```python
def cached_custom_embedding(db: Database, file: FileSnapshot, chunks: List[str]) -> int:
    with db.get_connection() as conn:
        with conn.cursor() as cur:
            for idx, chunk_text in enumerate(chunks):
                # Вычислить хэш чанка
                text_hash = hashlib.sha256(chunk_text.encode()).hexdigest()
                
                # Проверить кэш
                cur.execute(
                    "SELECT embedding FROM embedding_cache WHERE text_hash = %s",
                    (text_hash,)
                )
                row = cur.fetchone()
                
                if row:
                    # Использовать из кэша
                    embedding_str = row[0]
                else:
                    # Запросить у Ollama
                    response = requests.post(...)
                    embedding = response.json()['embedding']
                    embedding_str = '[' + ','.join(map(str, embedding)) + ']'
                    
                    # Сохранить в кэш
                    cur.execute(
                        "INSERT INTO embedding_cache (text_hash, embedding) VALUES (%s, %s::vector)",
                        (text_hash, embedding_str)
                    )
                
                # Вставить чанк
                cur.execute("INSERT INTO chunks ...")
        
        conn.commit()
```

**Преимущества:**
- Быстрее для повторяющихся чанков
- Экономия GPU

**Недостатки:**
- Больше места в БД
- Нужна стратегия очистки старых кэшей

### 9.4 Добавить метрики и мониторинг

**Шаг 1:** Добавить Prometheus exporter

```python
# utils/metrics.py
from prometheus_client import Counter, Histogram, start_http_server

FILES_PROCESSED = Counter('files_processed_total', 'Total files processed')
PARSING_TIME = Histogram('parsing_duration_seconds', 'Time spent parsing')
EMBEDDING_TIME = Histogram('embedding_duration_seconds', 'Time spent creating embeddings')

def init_metrics(port: int = 9090):
    start_http_server(port)
```

**Шаг 2:** Использовать в коде

```python
# В IngestDocument
import time
from utils.metrics import FILES_PROCESSED, PARSING_TIME

def __call__(self, file: FileSnapshot) -> bool:
    start = time.time()
    
    # Парсинг
    with PARSING_TIME.time():
        file.raw_text = parser.parse(file)
    
    # ... остальная логика
    
    FILES_PROCESSED.inc()
    return True
```

**Шаг 3:** Настроить Grafana

- Подключить Prometheus к `http://localhost:9090`
- Создать дашборд с графиками
- Алерты на ошибки

---

## 10. Почему именно так

### 10.1 Почему слоистая архитектура?

**Преимущества:**
- Чёткое разделение ответственности
- Легко тестировать каждый слой изолированно
- Можно менять инфраструктуру без изменения бизнес-логики

**Альтернативы:**
- **Монолит без слоёв** — быстрее для маленьких проектов, но сложно масштабировать
- **Микросервисы** — overkill для одного домена (обработка документов)

**Почему не микросервисы?**
- Дополнительная сложность (сеть, деплой, мониторинг)
- Нет необходимости независимого масштабирования частей
- Можно легко разделить позже, если нужно

### 10.2 Почему Dependency Injection через bootstrap?

**Преимущества:**
- Явные зависимости (видно в сигнатуре)
- Легко подменить в тестах
- Один источник правды (bootstrap)

**Альтернативы:**
- **Service Locator** — скрытые зависимости, сложно тестировать
- **Глобальные переменные** — race conditions, сложно изолировать

**Пример проблемы без DI:**

```python
# Плохо: глобальный объект
db = PostgresFileRepository(DATABASE_URL)

def process_file(file):
    db.mark_as_ok(file)  # Невозможно подменить в тестах
```

**С DI:**

```python
# Хорошо: зависимость передаётся явно
def process_file(file, db: Database):
    db.mark_as_ok(file)

# В тестах
mock_db = MockDatabase()
process_file(file, mock_db)  # Легко!
```

### 10.3 Почему ThreadPoolExecutor, а не asyncio?

**Аргументы за потоки:**
- Парсинг — CPU-bound (не получает пользы от asyncio)
- Семафоры контролируют параллелизм
- Проще код (нет async/await везде)

**Когда asyncio был бы лучше:**
- Если бы было много IO-bound операций без CPU-bound
- Если нужны тысячи параллельных соединений

**Текущий профиль:**
- 80% времени — парсинг (CPU)
- 15% времени — эмбеддинг (HTTP + GPU, контролируется семафором)
- 5% времени — БД (быстрые операции)

### 10.4 Почему PostgreSQL + pgvector, а не специализированная vector DB?

**Преимущества PostgreSQL:**
- Уже знакомая технология
- ACID транзакции для файлов и чанков
- Не нужен отдельный сервис
- pgvector достаточно быстр для миллионов векторов

**Альтернативы:**
- **Pinecone** — managed, но дорого и зависимость от облака
- **Weaviate** — специализированная, но дополнительная сложность
- **Milvus** — очень быстрая, но overkill для текущего масштаба

**Когда перейти на vector DB:**
- Если объём > 10 млн документов
- Если нужен очень быстрый ANN search
- Если pgvector становится узким местом

### 10.5 Почему отдельный FileWatcher сервис?

**Преимущества:**
- Worker может падать и перезапускаться
- Можно запустить несколько Worker'ов
- FileWatcher легковесный (Node.js)

**Альтернативы:**
- **Watchdog в Worker** — проще, но нет горизонтального масштабирования
- **Message queue (RabbitMQ)** — избыточно для текущего масштаба

---

## Заключение

Теперь вы понимаете:

1. **Структуру:** Domain → Application → Infrastructure → Bootstrap
2. **Компоненты:** Парсеры, чанкеры, эмбеддеры, use-case'ы
3. **Зависимости:** Как они собираются и внедряются
4. **Процесс:** От файла на диске до векторов в БД
5. **Расширение:** Как добавлять новые форматы/стратегии
6. **Решения:** Почему выбраны именно эти технологии

### Куда двигаться дальше?

- Улучшить чанкинг (семантический, с перекрытием)
- Добавить метрики и мониторинг
- Реализовать векторный поиск (query endpoint)
- Добавить кэширование эмбеддингов
- Web-интерфейс для управления

### Полезные команды

```bash
# Запустить всё
cd ~/supabase/docker && docker compose up -d
cd ~/alpaca/services && docker compose up -d
cd ~/alpaca && source venv/bin/activate && python main.py

# Посмотреть логи
docker logs -f alpaca-filewatcher-1
docker logs -f alpaca-ollama-1

# Проверить БД
psql $DATABASE_URL -c "SELECT status_sync, COUNT(*) FROM files GROUP BY status_sync"

# Тесты
python tests/runner.py --suite all
```

Удачи в разработке! 🚀

---

## Приложение: Миграция на упрощённую архитектуру

### Что изменилось (краткая сводка)

| Компонент | Старая версия | Новая версия | Причина |
|-----------|---------------|--------------|---------|
| **Domain facades** | `set_chunker()`, `get_embedder()` | Удалены | Глобальное состояние |
| **FileService** | Отдельный класс | Удалён | Тонкая обёртка |
| **WorkerApplication** | 10 полей | 2 поля | Избыточная экспозиция |
| **Bootstrap** | 8 функций, 230 строк | 1 функция, 60 строк | Упрощение |
| **ParserRegistry** | Фабрики `Callable[[], Parser]` | Экземпляры `Parser` | Ненужная индирекция |

### Как читать код после миграции

**1. Найти зависимости:**

```python
# Старый код: неясно, откуда берётся chunker
from core.domain.document_processing import chunk_document
chunks = chunk_document(file)  # Магия! Откуда chunker?

# Новый код: явная зависимость
@dataclass
class IngestDocument:
    chunker: Chunker  # ← видно в сигнатуре
    
    def __call__(self, file):
        chunks = self.chunker(file)  # ← понятно, откуда
```

**2. Создать use-case для тестов:**

```python
# Старый код: нужно настроить глобальное состояние
from core.domain.document_processing import set_chunker
set_chunker(mock_chunker)
ingest = IngestDocument(...)

# Новый код: передать в конструктор
ingest = IngestDocument(
    chunker=mock_chunker,  # ← просто передать
    ...
)
```

**3. Добавить новый парсер:**

```python
# Старый код: создать build-функцию
def build_my_parser(): return MyParser()
# Добавить в registry через tuple с фабрикой

# Новый код: создать экземпляр в bootstrap
my_parser = MyParser()
parser_registry = ParserRegistry(parsers={
    (".my",): my_parser,  # ← добавить одну строку
})
```

### Дополнительные ресурсы

- **ARCHITECTURE_SIMPLE.md** — актуальное описание архитектуры (370 строк)
- **REFACTORING_REPORT.md** — детальный отчёт об упрощении с метриками
- **architecture_roadmap.md** — история развития (этапы 1-6)
- **tests/** — примеры использования API в тестах

### FAQ по миграции

**Q: Почему старая архитектура была сложной?**  
A: Clean Architecture отлично подходит для больших проектов (5+ разработчиков, множество интерфейсов). Для ALPACA (1-2 разработчика, один Worker) она добавляла complexity без benefits.

**Q: Можно ли вернуться к старой версии?**  
A: Да, git истории сохранены. Но текущая версия проще и все тесты проходят.

**Q: Как обновить свои форки/расширения?**  
A: Следуйте паттерну из `bootstrap.py` — создавайте экземпляры напрямую, передавайте через конструкторы.

---

**Версия документа:** Январь 2025 (после упрощения)  
**Для актуальной архитектуры:** См. `ARCHITECTURE_SIMPLE.md`
