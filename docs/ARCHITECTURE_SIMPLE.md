# ALPACA: Упрощённая архитектура (после рефакторинга)

> **Версия:** После упрощения (убраны domain facades, FileService, сложный bootstrap)  
> **Дата:** Январь 2025  
> **Статус:** Актуально

---

## Зачем был рефакторинг?

Первая версия архитектуры следовала паттернам Clean Architecture с:
- Domain facades (глобальные `set_chunker`, `set_embedder`, `configure_parser_registry`)
- Дополнительным слоем FileService между use-case и repository
- Bootstrap из 8 отдельных функций, собирающих зависимости

**Проблема:** Код стал слишком сложным для понимания, много уровней абстракции, неявная глобальная конфигурация.

**Решение:** Упростили до минимума, убрав лишние слои, оставив только то, что действительно нужно.

---

## Новая структура

### Общая схема

```
monitored_folder/ 
    ↓ (сканирует)
FileWatcher (Node.js) 
    ↓ (GET /api/next-file)
Worker.start() 
    ↓ (для каждого файла)
ProcessFileEvent(file_info)
    ↓
IngestDocument(file_snapshot)
    ↓
parse → chunk → embed → PostgreSQL
```

### Файловая структура

```
alpaca/
├── core/
│   ├── domain/                          # Контракты и модели
│   │   ├── files/
│   │   │   ├── models.py               # FileSnapshot (dataclass)
│   │   │   └── repository.py           # FileRepository (Protocol)
│   │   └── document_processing/
│   │       ├── parsers/
│   │       │   ├── base.py             # ParserProtocol
│   │       │   └── registry.py         # ParserRegistry (класс)
│   │       ├── chunkers/
│   │       │   └── __init__.py         # Chunker (тип)
│   │       └── embedders/
│   │           └── __init__.py         # Embedder (тип)
│   │
│   ├── application/                     # Реализации и use-cases
│   │   ├── files/
│   │   │   ├── use_cases.py           # ResetStuckFiles, DequeueNextFile
│   │   │   └── (deprecated service.py удалён)
│   │   ├── processing/
│   │   │   └── use_cases.py           # IngestDocument, ProcessFileEvent
│   │   ├── document_processing/
│   │   │   ├── parsers/               # WordParser, PDFParser, etc.
│   │   │   ├── chunking/              # chunk_document()
│   │   │   └── embedders/             # custom_embedding, langchain_embedding
│   │   └── bootstrap.py               # ⭐ build_worker_application()
│   │
│   └── infrastructure/                  # Адаптеры к внешним системам
│       └── database/
│           └── postgres.py             # PostgresFileRepository
│
├── utils/
│   ├── logging.py                      # setup_logging, get_logger
│   └── worker.py                       # Worker (класс управления потоками)
│
├── main.py                             # Точка входа
├── settings.py                         # Конфигурация
└── tests/                              # Тесты
```

---

## Ключевые компоненты

### 1. Bootstrap (core/application/bootstrap.py)

**Единственная функция:** `build_worker_application(settings)`

```python
@dataclass
class WorkerApplication:
    """Контейнер с готовыми зависимостями для приложения."""
    worker: Worker           # Менеджер потоков
    repository: FileRepository  # Доступ к БД

def build_worker_application(settings) -> WorkerApplication:
    # 1. Создать repository
    repository = PostgresFileRepository(settings.DATABASE_URL)
    
    # 2. Создать парсеры
    word_parser = WordParser(...)
    pdf_parser = PDFParser(...)
    # ... и т.д.
    
    # 3. Собрать registry
    parser_registry = ParserRegistry({
        (".doc", ".docx"): word_parser,
        (".pdf",): pdf_parser,
        # ...
    })
    
    # 4. Создать chunker и embedder
    chunker = chunk_document  # функция из application
    embedder = custom_embedding  # или langchain_embedding
    
    # 5. Создать IngestDocument
    ingest = IngestDocument(
        repository=repository,
        parser_registry=parser_registry,
        chunker=chunker,
        embedder=embedder
    )
    
    # 6. Создать ProcessFileEvent
    process_file = ProcessFileEvent(
        ingest_document=ingest,
        repository=repository
    )
    
    # 7. Создать Worker
    worker = Worker(
        db=repository,
        filewatcher_api_url=settings.FILEWATCHER_API_URL,
        process_file_func=process_file
    )
    
    return WorkerApplication(worker=worker, repository=repository)
```

**Что изменилось:**
- ❌ Убрали 8 отдельных функций (`build_word_parser`, `build_pdf_parser`, ...)
- ❌ Убрали глобальную конфигурацию фасадов (`set_chunker`, `set_embedder`)
- ✅ Всё создаётся в одной функции, зависимости явные
- ✅ WorkerApplication содержит только `worker` и `repository` (было 10 полей)

---

### 2. Domain Layer (контракты)

**Никакой логики, только типы и интерфейсы.**

#### FileSnapshot (domain/files/models.py)

```python
@dataclass
class FileSnapshot:
    hash: str          # SHA256
    path: str          # относительно MONITORED_PATH
    size: int
    mtime: float
    status_sync: str   # added/updated/deleted/processed/ok/error
```

#### FileRepository (domain/files/repository.py)

```python
class FileRepository(Protocol):
    """Контракт для работы с базой файлов и чанков."""
    
    def mark_as_ok(self, file_hash: str) -> None: ...
    def mark_as_error(self, file_hash: str) -> None: ...
    def mark_as_processed(self, file_hash: str) -> None: ...
    def set_raw_text(self, file_hash: str, text: str) -> None: ...
    def delete_chunks_by_hash(self, file_hash: str) -> None: ...
    def delete_file_by_hash(self, file_hash: str) -> None: ...
    # ... методы для чанков
```

#### Типы для пайплайна

```python
# Chunker: превращает файл в список чанков
Chunker = Callable[[FileSnapshot], List[Chunk]]

# Embedder: создаёт эмбеддинги и сохраняет в БД
Embedder = Callable[[List[Chunk], FileSnapshot, FileRepository], int]

# ParserProtocol: парсит файл в текст
class ParserProtocol(Protocol):
    def parse(self, file: FileSnapshot) -> Optional[str]: ...
```

**Что изменилось:**
- ❌ Убрали глобальные `_chunker`, `_embedder`, `_parser_registry`
- ❌ Убрали функции `set_chunker()`, `get_chunker()`, `configure_parser_registry()`
- ✅ Оставили только типы (type aliases и Protocol)

---

### 3. Application Layer (логика)

#### IngestDocument (application/processing/use_cases.py)

**Главный use-case обработки файла:**

```python
@dataclass
class IngestDocument:
    repository: FileRepository
    parser_registry: ParserRegistry
    chunker: Chunker
    embedder: Embedder
    
    def __call__(self, file: FileSnapshot) -> bool:
        # 1. Parse
        parser = self.parser_registry.get_parser(file.path)
        parsed_text = parser.parse(file)
        if not parsed_text:
            self.repository.mark_as_error(file.hash)
            return False
        
        # 2. Save raw text
        self.repository.set_raw_text(file.hash, parsed_text)
        self._save_to_disk(file, parsed_text)
        
        # 3. Chunk
        chunks = self.chunker(file)
        if not chunks:
            self.repository.mark_as_error(file.hash)
            return False
        
        # 4. Embed
        count = self.embedder(chunks, file, self.repository)
        if count == 0:
            self.repository.mark_as_error(file.hash)
            return False
        
        # 5. Mark as ok
        self.repository.mark_as_ok(file.hash)
        return True
```

**Что изменилось:**
- ❌ Убрали зависимость от FileService (тонкая обёртка над repository)
- ✅ Напрямую используем `repository.mark_as_ok()`, `repository.set_raw_text()`
- ✅ Добавили внутренний метод `_save_to_disk()` для сохранения .md файлов

#### ProcessFileEvent (application/processing/use_cases.py)

**Use-case для реакции на события FileWatcher:**

```python
@dataclass
class ProcessFileEvent:
    ingest_document: IngestDocument
    repository: FileRepository
    
    def __call__(self, file_info: Dict[str, Any]) -> bool:
        file = FileSnapshot(**file_info)
        
        if file.status_sync == "deleted":
            self.repository.delete_chunks_by_hash(file.hash)
            self.repository.delete_file_by_hash(file.hash)
            return True
        
        if file.status_sync == "updated":
            self.repository.delete_chunks_by_hash(file.hash)
            return self.ingest_document(file)
        
        if file.status_sync == "added":
            return self.ingest_document(file)
        
        return False
```

**Что изменилось:**
- ❌ Убрали использование FileService
- ✅ Напрямую вызываем методы repository

#### ParserRegistry (domain/document_processing/parsers/registry.py)

**Простой маппинг расширений на парсеры:**

```python
class ParserRegistry:
    def __init__(self, parsers: Dict[Tuple[str, ...], ParserProtocol]):
        self._parsers = parsers
    
    def get_parser(self, file_path: str) -> ParserProtocol:
        ext = Path(file_path).suffix.lower()
        for extensions, parser in self._parsers.items():
            if ext in extensions:
                return parser
        raise ValueError(f"No parser for extension: {ext}")
```

**Что изменилось:**
- ❌ Убрали фабрики `Callable[[], ParserProtocol]`
- ❌ Убрали глобальный `_parser_registry` и `configure_parser_registry()`
- ✅ Принимает готовые экземпляры парсеров
- ✅ Простой словарь, никакой магии

---

### 4. Worker (utils/worker.py)

**Менеджер параллельной обработки:**

```python
class Worker:
    def __init__(
        self,
        db: Database,
        filewatcher_api_url: str,
        process_file_func: Callable[[Dict[str, Any]], bool]
    ):
        self.db = db
        self.filewatcher_api_url = filewatcher_api_url
        self.process_file = process_file_func  # ProcessFileEvent
    
    def start(self, poll_interval: int = 5, max_workers: int = 5):
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            while True:
                file = self._get_next_file()
                if file:
                    self.db.mark_as_processed(file['hash'])
                    executor.submit(self.process_file, file)
                else:
                    time.sleep(poll_interval)
```

**Что НЕ изменилось:**
- Worker остался таким же, только переименовали параметр `process_file_func`

---

## Процесс запуска

### 1. main.py

```python
from core.application.bootstrap import build_worker_application
from settings import settings

if __name__ == "__main__":
    setup_logging()
    
    # Собрать зависимости
    app = build_worker_application(settings)
    
    # Сбросить зависшие файлы
    app.repository.reset_processed_statuses()
    
    # Запустить worker
    app.worker.start(
        poll_interval=settings.WORKER_POLL_INTERVAL,
        max_workers=settings.WORKER_MAX_CONCURRENT_FILES
    )
```

### 2. Что происходит

1. `build_worker_application()` создаёт все зависимости
2. `repository.reset_processed_statuses()` сбрасывает зависшие файлы
3. `worker.start()` запускает цикл обработки:
   - Опрашивает FileWatcher API
   - Получает файл → помечает как `processed`
   - Передаёт в `ProcessFileEvent`
   - `ProcessFileEvent` вызывает `IngestDocument`
   - `IngestDocument` выполняет parse → chunk → embed
   - Файл помечается как `ok` или `error`

---

## Как расширять

### Добавить новый парсер

1. Создать класс в `core/application/document_processing/parsers/`:

```python
class MyParser:
    def parse(self, file: FileSnapshot) -> Optional[str]:
        # логика парсинга
        return text
```

2. Зарегистрировать в `bootstrap.py`:

```python
my_parser = MyParser(...)
parser_registry = ParserRegistry({
    (".doc", ".docx"): word_parser,
    (".myext",): my_parser,  # ← добавить сюда
    # ...
})
```

### Добавить новый embedder

1. Создать функцию в `core/application/document_processing/embedders/`:

```python
def my_embedding(
    chunks: List[Chunk],
    file: FileSnapshot,
    repository: FileRepository
) -> int:
    # логика эмбеддинга
    return saved_count
```

2. Переключить в `bootstrap.py`:

```python
embedder = my_embedding  # вместо custom_embedding
```

### Добавить новый use-case

1. Создать класс в `core/application/<область>/use_cases.py`:

```python
@dataclass
class MyUseCase:
    repository: FileRepository
    
    def __call__(self, params) -> result:
        # логика
        pass
```

2. Создать в `bootstrap.py` и добавить в `WorkerApplication` (если нужен глобальный доступ)

---

## Почему так упростили?

### Было (Clean Architecture)

```
User Request
    ↓
Domain Facades (set_chunker, set_embedder, configure_parser_registry)
    ↓
FileService (тонкая обёртка над Repository)
    ↓
Repository
    ↓
Database
```

**Проблемы:**
- Глобальное состояние (`_chunker`, `_embedder`, `_parser_registry`)
- Лишний слой FileService без бизнес-логики
- Bootstrap из 8 функций для создания зависимостей
- Сложно понять поток данных

### Стало (Упрощённое)

```
User Request
    ↓
Use-Case (ProcessFileEvent, IngestDocument)
    ↓
Repository
    ↓
Database
```

**Преимущества:**
- Явные зависимости через конструкторы
- Нет глобального состояния
- Bootstrap в одной функции (~60 строк)
- Прямой поток данных

### Когда Clean Architecture избыточна

Clean Architecture подходит для больших проектов с:
- Несколькими интерфейсами (Web, CLI, gRPC)
- Сменяемыми хранилищами (PostgreSQL → MongoDB)
- Большой командой разработчиков

Для ALPACA (малый проект, 1-2 разработчика, стабильный стек) Clean Architecture добавляет сложность без выгоды.

---

## Резюме изменений

### Удалено

- ❌ `core/domain/document_processing/chunkers/__init__.py`: функции `set_chunker`, `get_chunker`
- ❌ `core/domain/document_processing/embedders/__init__.py`: функции `set_embedder`, `get_embedder`
- ❌ `core/domain/document_processing/parsers/registry.py`: глобальный `_parser_registry`, `configure_parser_registry`
- ❌ `core/application/files/service.py`: FileService (тонкая обёртка)
- ❌ `core/application/bootstrap.py`: 8 отдельных `build_*` функций

### Упрощено

- ✅ `WorkerApplication`: 10 полей → 2 поля (worker, repository)
- ✅ `ParserRegistry`: фабрики → прямые экземпляры
- ✅ `IngestDocument`: использует repository напрямую, не через FileService
- ✅ `ProcessFileEvent`: использует repository напрямую
- ✅ Bootstrap: 230 строк → 60 строк, одна функция

### Сохранено

- ✅ Domain типы (FileSnapshot, FileRepository, ParserProtocol, Chunker, Embedder)
- ✅ Application реализации (парсеры, чанкеры, эмбеддеры)
- ✅ Infrastructure адаптеры (PostgresFileRepository)
- ✅ Тесты (39 тестов проходят)

---

## Следующие шаги

1. ✅ **Упрощение завершено** — архитектура понятна, тесты проходят
2. 🔲 **Обновить ARCHITECTURE_DETAILED.md** — переписать под новую структуру
3. 🔲 **Добавить примеры расширения** — показать как добавлять фичи
4. 🔲 **Документировать настройки** — описать все переменные в settings.py

---

## Микросервисы

### File Watcher

**Расположение:** `services/file_watcher/`

**Что это:** Node.js/Python сервис для сканирования `monitored_folder` и предоставления API (порт 8081)

**Архитектура:**
```
services/file_watcher/
  src/
    main.py          # Entrypoint: запуск API + Scanner
    api.py           # FastAPI эндпоинты
    service.py       # FileWatcherService
    scanner.py       # Сканирование диска
    vector_sync.py   # Синхронизация file_state ↔ chunks
  Dockerfile         # Копирует core/ из основного проекта
```

**Что использует из core:**
- `PostgresFileRepository` - для работы с БД
- `DequeueNextFile` - use-case для получения файла из очереди
- `GetQueueStats` - use-case для статистики
- `SyncFilesystemSnapshot` - use-case для синхронизации файлов

**API эндпоинты:**
- `GET /api/next-file` - получить следующий файл для обработки (приоритет: deleted → updated → added)
- `GET /api/queue/stats` - статистика очереди

**Процесс работы:**
1. Scanner периодически сканирует диск
2. Результаты сравниваются с таблицей `files`
3. Обновляются статусы (`added`, `updated`, `deleted`)
4. Worker опрашивает `/api/next-file` и берёт файлы на обработку

**Почему использует use-cases напрямую?**

FileWatcher - это микросервис, который работает с той же БД, что и Worker. Использование `DequeueNextFile` и других use-cases из `core/application/files` обеспечивает:
- Переиспользование бизнес-логики
- Единый контракт для работы с очередью
- Консистентность приоритетов обработки

### Admin Backend

**Расположение:** `services/admin_backend/`

**Что это:** FastAPI-сервис для мониторинга системы (порт 8080)

**Архитектура:**
```
services/admin_backend/
  src/
    main.py          # FastAPI эндпоинты
    database.py      # Фасад для статистики
  Dockerfile         # Копирует core/ из основного проекта
```

**Почему своя database.py?**

Admin Backend - это **отдельный микросервис** с собственными нуждами:
- Дашборды с агрегацией данных
- Health checks БД
- Статистика по обработке

`FileRepository` (domain контракт) предназначен для Worker'а (CRUD операций). 
Не стоит засорять его методами мониторинга (`get_file_state_stats`, `get_database_health`).

**Что использует из core:**
- `PostgresFileRepository` - для подключения к БД
- Domain модели - для совместимости типов

**Общий паттерн микросервисов:**
```dockerfile
# Все микросервисы копируют core/ библиотеку
COPY core /opt/alpaca/core
COPY utils /opt/alpaca/utils
ENV PYTHONPATH="/opt/alpaca:${PYTHONPATH}"
```

Это правильная архитектура: микросервисы переиспользуют инфраструктурный слой (`PostgresFileRepository`) и use-cases (`DequeueNextFile`, `SyncFilesystemSnapshot`), но имеют свои специфичные API.

---

## Вопросы?

**Q: Почему domain всё ещё отдельно?**  
A: Domain содержит контракты (Protocol, type aliases), которые не зависят от реализаций. Это полезно для тестирования (mock'ов) и понимания интерфейсов.

**Q: Можно ли ещё упростить?**  
A: Да, можно убрать domain и application слои, сделать всё в одном файле. Но текущая структура даёт баланс между простотой и расширяемостью.

**Q: Почему Admin Backend не использует FileRepository напрямую?**  
A: Admin Backend - отдельный микросервис с мониторинговыми методами (статистика, health checks). FileRepository - контракт для Worker'а (CRUD). У них разные задачи.

**Q: Почему FileWatcher использует use-cases из core/application?**  
A: FileWatcher и Worker работают с одной очередью. Использование `DequeueNextFile` обеспечивает консистентную логику приоритетов и предотвращает дублирование кода.

**Q: Не нарушает ли это принцип независимости микросервисов?**  
A: Нет. FileWatcher и Worker - это части одной распределённой системы, работающие с общей БД. Они разделяют domain-контракты (Protocol) и use-cases, что правильно. Полная изоляция (с дублированием логики) была бы избыточной для этого проекта.

**Q: Как переключиться на langchain embedder?**  
A: В `bootstrap.py` замените `embedder = custom_embedding` на `embedder = langchain_embedding`.

**Q: Как добавить новый статус файла?**  
A: Добавьте обработку в `ProcessFileEvent.__call__()` и обновите логику FileWatcher.

---

**Версия:** После рефакторинга упрощения (январь 2025)  
**Контакт:** Документ актуален для текущей кодовой базы
