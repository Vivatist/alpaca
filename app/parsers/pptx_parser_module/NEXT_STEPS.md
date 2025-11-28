# Следующие шаги для запуска PPTX Parser

## 1️⃣ Установка зависимостей (для локальной разработки)

```bash
cd /c/Users/Andrey/Alpaca

# Установить python-pptx (обязательно)
pip install python-pptx>=0.6.21

# Установить unstructured с PPTX (рекомендуется для лучшего качества)
pip install "unstructured[pptx]"

# Проверка установки
python -c "from pptx import Presentation; print('✓ python-pptx OK')"
python -c "from unstructured.partition.pptx import partition_pptx; print('✓ unstructured OK')"
```

## 2️⃣ Тестирование парсера

```bash
# Базовые тесты (работают без файлов)
python tests/test_pptx_parser.py

# Ожидаемый вывод:
# ✓ Parser initialized
# ✓ Parser has 'parse' method
# ✓ Parser returns correct structure
# ✓ Parser handles missing files correctly
# All tests passed!
```

## 3️⃣ Тест с реальным PPTX файлом

```bash
# Если у вас есть .pptx файл
python tests/test_pptx_parser.py --file /path/to/your/presentation.pptx

# Парсер выведет:
# - Метаданные (автор, слайды, размер)
# - Превью Markdown (первые 500 символов)
# - Сохранит результат в presentation_parsed.md
```

## 4️⃣ Прямой запуск парсера

```bash
# Парсинг файла с выводом на экран
python document-processors/src/parsers/pptx/pptx_parser.py presentation.pptx

# Парсинг с сохранением в файл
python document-processors/src/parsers/pptx/pptx_parser.py presentation.pptx -o output.md
```

## 5️⃣ Использование в коде

Создайте тестовый скрипт `test_my_pptx.py`:

```python
from document_processors.src.parsers.pptx import PptxParser

# Инициализация
parser = PptxParser()

# Парсинг вашего файла
result = parser.parse("path/to/your/file.pptx")

if result['success']:
    print(f"✓ Успешно!")
    print(f"  Слайдов: {result['metadata']['slides']}")
    print(f"  Автор: {result['metadata']['author']}")
    print(f"  Размер текста: {len(result['markdown'])} символов")
    
    # Сохранение
    parser.save_to_markdown_file(result, "output.md")
    print("✓ Сохранено в output.md")
else:
    print(f"✗ Ошибка: {result['error']}")
```

Запуск:
```bash
python test_my_pptx.py
```

## 6️⃣ Интеграция с file-watcher

Парсер уже готов к интеграции. В file-watcher добавьте обработку `.pptx`:

```python
from document_processors.src.parsers.pptx import PptxParser

# В обработчике файлов
if file_path.endswith('.pptx'):
    parser = PptxParser()
    result = parser.parse(file_path, file_hash=watcher_hash)
    
    if result['success']:
        # Отправка в Dify
        send_to_dify(result['yaml_header'] + result['markdown'])
```

## 7️⃣ Проверка в Docker

```bash
# Пересборка образа с новыми зависимостями
docker compose build document-processors

# Запуск контейнера
docker compose up -d document-processors

# Проверка логов
docker compose logs -f document-processors
```

## 8️⃣ Мониторинг в Grafana

После первого парсинга проверьте логи:

1. Откройте Grafana: http://localhost:3001
2. Login: admin / alpaca123
3. Explore → Loki
4. Запрос: `{service="pptx-parser"}`
5. Должны увидеть логи парсинга

## 📚 Документация

- **QUICKSTART.md** - краткое руководство
- **README.md** - полная документация
- **INSTALL.md** - установка зависимостей
- **SUMMARY.md** - итоги реализации

## ❓ Troubleshooting

### Ошибка "No module named 'pptx'"
```bash
pip install python-pptx>=0.6.21
```

### Ошибка "No module named 'unstructured'"
```bash
pip install "unstructured[pptx]"
```

Парсер будет работать только с python-pptx (fallback режим), но качество ниже.

### Тесты не проходят
```bash
# Убедитесь что в правильной директории
cd /c/Users/Andrey/Alpaca

# Проверьте Python пути
python -c "import sys; print('\n'.join(sys.path))"
```

### Плохое качество парсинга
Убедитесь что установлен unstructured для лучшего качества:
```bash
pip install "unstructured[pptx]"
```

---

**Готово к использованию!** ✅

Парсер полностью реализован и протестирован. Начните с шага 1 (установка зависимостей) и далее по порядку.
