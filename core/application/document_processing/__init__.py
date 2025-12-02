"""
Реализации компонентов обработки документов.

=== НАЗНАЧЕНИЕ ===
Модуль содержит конкретные реализации компонентов пайплайна:

=== СТРУКТУРА ===
- parsers/     — парсеры документов (WordParser, PDFParser, ...)
- chunkers/    — функции разбиения на чанки
- embedders/   — функции создания эмбеддингов

=== ИСПОЛЬЗОВАНИЕ ===

    # Парсеры
    from core.application.document_processing.parsers import (
        WordParser, PDFParser, PowerPointParser, ExcelParser, TXTParser
    )
    parser = WordParser(enable_ocr=True)
    text = parser.parse(file)

    # Чанкинг
    from core.application.document_processing.chunkers import chunk_document
    chunks = chunk_document(file)  # List[str]

    # Эмбеддинг
    from core.application.document_processing.embedders import (
        embed_chunks, custom_embedding, langchain_embedding
    )
    count = embed_chunks(repo, file, chunks)  # использует custom_embedding

=== РЕАЛИЗАЦИИ ===
Парсеры:
- WordParser — python-docx + MarkItDown + OCR (.doc, .docx)
- PDFParser — PyMuPDF + fallback Unstructured (.pdf)
- PowerPointParser — python-pptx (.ppt, .pptx)
- ExcelParser — openpyxl (.xls, .xlsx)
- TXTParser — chardet для кодировки (.txt)

Чанкеры:
- chunking() — fixed-size по 1000 символов

Эмбеддеры:
- custom_embedding — Ollama bge-m3 (бесплатно, локально)
- langchain_embedding — LangChain/OpenAI (платно)
"""

