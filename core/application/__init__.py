"""
Слой приложения (Application Layer) для ALPACA.

=== НАЗНАЧЕНИЕ ===
Слой приложения содержит реализации use-case'ов и сервисов,
оркестрирующих доменные модели и инфраструктуру:

- Use Cases (IngestDocument, ProcessFileEvent) — бизнес-логика
- Парсеры (WordParser, PDFParser, ...) — извлечение текста
- Чанкеры (chunking) — разбиение на части
- Эмбеддеры (custom_embedding, langchain_embedding) — векторизация
- Bootstrap — сборка зависимостей

=== СТРУКТУРА ===
- core/application/processing/    — use-case'ы обработки файлов
- core/application/files/         — use-case'ы управления файлами
- core/application/document_processing/  — реализации парсеров/чанкеров/эмбеддеров
- core/application/bootstrap.py   — фабрика зависимостей

=== ИСПОЛЬЗОВАНИЕ ===

    # Сборка приложения
    from core.application.bootstrap import build_worker_application
    app = build_worker_application(settings)
    app.worker.start()

    # Импорт use-case'ов
    from core.application.processing import IngestDocument, ProcessFileEvent

    # Импорт парсеров
    from core.application.document_processing.parsers import WordParser

=== ПРИНЦИПЫ ===
- Application реализует КАК работает система
- Зависит от Domain (модели, контракты)
- Зависит от Infrastructure (БД, API)
- Зависимости внедряются через конструкторы (DI)
"""
