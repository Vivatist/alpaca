# Быстрая установка зависимостей для PPTX Parser

## Для локальной разработки:

```bash
# Перейти в корень проекта
cd /c/Users/Andrey/Alpaca

# Установить python-pptx (обязательно)
pip install python-pptx>=0.6.21

# Установить unstructured с поддержкой PPTX (рекомендуется)
pip install "unstructured[pptx]"

# Или установить все зависимости document-processors
pip install -r document-processors/requirements.txt
```

## Проверка установки:

```bash
python -c "from pptx import Presentation; print('✓ python-pptx OK')"
python -c "from unstructured.partition.pptx import partition_pptx; print('✓ unstructured OK')"
```

## Тестирование парсера:

```bash
# Базовые тесты (работают без реальных файлов)
python tests/test_pptx_parser.py

# Тест с вашим PPTX файлом
python tests/test_pptx_parser.py --file /path/to/presentation.pptx

# Прямой запуск парсера
python document-processors/src/parsers/pptx/pptx_parser.py /path/to/presentation.pptx -o output.md
```

## В Docker:

Зависимости уже включены в `document-processors/requirements.txt` и будут установлены при сборке образа:

```bash
docker compose build document-processors
```

## Минимальные требования:

- **python-pptx >= 0.6.21** - обязательно (fallback parser + метаданные)
- **unstructured[pptx]** - рекомендуется (лучшее качество парсинга + русский язык)

Парсер работает без unstructured, используя fallback на python-pptx, но качество будет хуже.
