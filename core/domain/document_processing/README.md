# Domain Document Processing

Этот пакет описывает публичный API доменного слоя для работы с парсерами, чанкерами и эмбеддерами.

## Ответственность

- Определяет протоколы (`ParserProtocol`, `Chunker`, `Embedder`) и реестры, необходимые приложению.
- Содержит минимальный стейт для активных реализаций (`configure_parser_registry`, `set_chunker`, `set_embedder`).
- Не знает о конкретных реализациях: объекты передаются сверху (через bootstrap) и могут быть заменены без изменения домена.

## Использование

1. На этапе bootstrap вызовите `configure_parser_registry(...)`, `set_chunker(...)` и `set_embedder(...)`, передав реализации из application-слоя.
2. Внешние модули должны импортировать только из доменного фасада (`core.domain.document_processing`). Например:
   ```python
   from core.domain.document_processing import get_parser_for_path, chunk_document
   ```
3. Любые новые реализации должны жить в `core/application/document_processing`, а в домен добавляются лишь новые протоколы/хелперы.

Такой подход гарантирует направленную зависимость: домен ← application, и упрощает тестирование/подмену реализаций.
