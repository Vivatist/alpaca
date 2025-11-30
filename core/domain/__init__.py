"""
Слой домена (Domain Layer) для ALPACA.

=== НАЗНАЧЕНИЕ ===
Доменный слой содержит ядро бизнес-логики, не зависящее от внешних систем:
- Модели данных (FileSnapshot, FileQueueItem)
- Интерфейсы репозиториев (FileRepository, Database)
- Контракты компонентов (ParserProtocol, Chunker, Embedder)
- Перечисления статусов (FileStatus)

Домен не знает о PostgreSQL, Ollama или файловой системе — это позволяет
легко тестировать и подменять реализации.

=== СТРУКТУРА ===
- core/domain/files/         — сущности файлов и репозиторий
- core/domain/document_processing/  — контракты парсеров, чанкеров, эмбеддеров

=== ИСПОЛЬЗОВАНИЕ ===
Обычно импортируют конкретные модули:

    from core.domain.files import FileSnapshot, FileRepository
    from core.domain.document_processing import ParserProtocol, Chunker

=== ПРИНЦИПЫ ===
- Домен описывает ЧТО делает система, а не КАК
- Зависимости инвертированы: Application зависит от Domain, не наоборот
- Все внешние системы скрыты за протоколами/интерфейсами
"""

__all__ = []
