# Application Document Processing

Здесь находятся конкретные реализации парсеров, чанкерa и эмбеддеров, которые подключаются к доменному фасаду во время bootstrap.

## Что внутри

- `parsers/` — реализации для DOCX, PDF, PPTX, XLS/XLSX, TXT и общие утилиты.
- `chunking/` — стратегия разбивки текста (по умолчанию `custom_chunker.chunking`).
- `embedding/` — клиенты Ollama (`custom_embedding`) и LangChain (`langchain_embedding`).

## Как использовать

1. Импортируйте нужные реализации в bootstrap и передайте их в домен через `set_chunker`, `set_embedder`, `configure_parser_registry`.
2. Для переключения эмбеддера используйте настройку `settings.EMBEDDER_BACKEND`. Bootstrap выберет `custom_embedding` или `langchain_embedding` и зарегистрирует его в домене.
3. Новые стратегии следует добавлять здесь, сохраняя чистые контракты домена.

Таким образом весь прикладной код зависит от доменного API, а конкретные реализации остаются заменяемыми.
