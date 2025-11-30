# Настройки и Bootstrap

Документ описывает, как конфигурация из `settings.py` управляет сборкой worker'а.

## Основные точки входа

- `settings.py` — единый источник значений по умолчанию. Любые несекретные параметры (пути, лимиты, фичефлаги) должны жить здесь.
- `.env` — только креденшелы и приватные URL, которые читаются `Settings(BaseSettings)`.
- `core/application/bootstrap.py` — строит репозиторий, сервисы и worker на основе настроек, а затем регистрирует реализации в доменном фасаде.

## EMBEDDER_BACKEND

Переключает реализацию эмбеддера без правок кода.

| Значение | Описание |
|----------|----------|
| `custom` (по умолчанию) | Использует `core.application.document_processing.embedding.custom_embedding` (HTTP к Ollama). |
| `langchain` | Подключает `langchain_embedding` (требуются зависимости LangChain/OpenAI). |

Пример смены реализации (bash):

```bash
export EMBEDDER_BACKEND=langchain
python main.py
```

Bootstrap выбирает функцию согласно настройке и вызывает `set_embedder(...)` доменного слоя, что делает переключение прозрачным для остального кода.

## Bootstrap в тестах

В тестах не нужно импортировать объекты из `main.py`. Вместо этого:

```python
from core.application.bootstrap import build_worker_application
bootstrap_app = build_worker_application(settings)
ingest_document = bootstrap_app.ingest_document
process_file_use_case = bootstrap_app.process_file_event
```

Pytest-файл `tests/conftest.py` предоставляет фикстуры (`worker_app`, `ingest_pipeline`, `process_file_use_case`), поэтому рекомендуется использовать их напрямую.

Следуя этим правилам, доменный слой остаётся независимым, а смена реализаций происходит через конфигурацию.
