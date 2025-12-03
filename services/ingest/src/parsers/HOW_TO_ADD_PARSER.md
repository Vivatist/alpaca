# Как добавить парсер для нового расширения

## Структура модуля parsers

```
parsers/
├── __init__.py           ← ParserRegistry + build_parser_registry()
├── base_parser.py        ← BaseParser (абстрактный класс)
├── document_converter.py ← Конвертер форматов
├── word/                 ← WordParser (.doc, .docx)
├── pdf/                  ← PDFParser (.pdf)
├── pptx/                 ← PowerPointParser (.ppt, .pptx)
├── excel/                ← ExcelParser (.xls, .xlsx)
├── txt/                  ← TXTParser (.txt)
└── xyz/                  ← ваш новый парсер (.xyz)
```

## Шаги (на примере расширения .xyz)

### 1. Создайте папку и файлы парсера

```bash
mkdir -p parsers/xyz
touch parsers/xyz/__init__.py
touch parsers/xyz/xyz_parser.py
```

### 2. Реализуйте парсер

Создайте файл `parsers/xyz/xyz_parser.py`:

```python
#!/usr/bin/env python3
"""
XYZ Parser для RAG системы ALPACA

Парсер файлов формата .xyz

Pipeline:
    .xyz → Your Logic → Text
"""

import os
from pathlib import Path
from typing import TYPE_CHECKING

from ..base_parser import BaseParser

if TYPE_CHECKING:
    from contracts import FileSnapshot


class XYZParser(BaseParser):
    """
    Парсер файлов формата XYZ.
    
    Использует pipeline:
    1. Чтение файла
    2. Извлечение текста
    3. Возврат результата
    """
    
    def __init__(self):
        """Инициализация парсера."""
        super().__init__("xyz-parser")
    
    def _parse(self, file: 'FileSnapshot') -> str:
        """
        Парсинг XYZ файла в текст.
        
        Args:
            file: FileSnapshot с информацией о файле
            
        Returns:
            str: Извлечённый текст
            
        Raises:
            FileNotFoundError: Если файл не найден
            ValueError: Если не удалось извлечь текст
        """
        file_path = file.full_path
        
        if not os.path.exists(file_path):
            self.logger.error(f"File not found | file={file.path}")
            raise FileNotFoundError(f"File not found | file={file.path}")
        
        self.logger.info(f"Parsing XYZ document | file={file.path}")
        
        try:
            # === ВАША ЛОГИКА ПАРСИНГА ===
            
            # Пример: чтение как текст
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Пример: использование библиотеки
            # import xyz_library
            # content = xyz_library.extract_text(file_path)
            
            # === КОНЕЦ ЛОГИКИ ===
            
            if not content.strip():
                raise ValueError(f"Empty content extracted | file={file.path}")
            
            self.logger.info(f"✅ Parsed XYZ | file={file.path} chars={len(content)}")
            return content
            
        except Exception as e:
            self.logger.error(f"❌ Failed to parse XYZ | file={file.path} error={e}")
            raise
```

### 3. Экспортируйте парсер из пакета

Создайте файл `parsers/xyz/__init__.py`:

```python
"""XYZ Parser для .xyz файлов."""

from .xyz_parser import XYZParser

__all__ = ["XYZParser"]
```

### 4. Добавьте импорт в `parsers/__init__.py`

```python
# В начале файла добавьте импорт
from .xyz.xyz_parser import XYZParser

# В функции build_parser_registry() добавьте расширение
def build_parser_registry() -> ParserRegistry:
    """Создать реестр парсеров с настройками по умолчанию."""
    return ParserRegistry({
        (".doc", ".docx"): WordParser(enable_ocr=True),
        (".pdf",): PDFParser(),
        (".ppt", ".pptx"): PowerPointParser(),
        (".xls", ".xlsx"): ExcelParser(),
        (".txt",): TXTParser(),
        (".xyz",): XYZParser(),  # ← новый парсер
    })
```

### 5. Добавьте зависимости (если нужны)

В `requirements.txt` добавьте библиотеки для парсинга:

```
xyz-library>=1.0.0
```

### 6. Пересоберите Docker-образ

```bash
cd services/ingest
docker build -t alpaca-ingest:latest .
```

## Правила написания парсеров

1. **Наследуйте от BaseParser**:
   ```python
   class XYZParser(BaseParser):
       def __init__(self):
           super().__init__("xyz-parser")
   ```

2. **Реализуйте метод `_parse()`**:
   ```python
   def _parse(self, file: FileSnapshot) -> str:
       # Возвращает извлечённый текст
   ```

3. **Используйте `file.full_path`** для доступа к файлу

4. **Бросайте исключения** при ошибках (базовый класс их обработает)

5. **Логируйте** важные события через `self.logger`

6. **Не возвращайте пустой текст** — базовый класс это проверит

## Структура FileSnapshot

```python
@dataclass
class FileSnapshot:
    hash: str           # SHA256 хэш файла
    path: str           # Относительный путь (monitored_folder/doc.xyz)
    full_path: str      # Абсолютный путь (/home/alpaca/monitored_folder/doc.xyz)
    raw_text: str = ""  # Заполняется после парсинга
```

## Пример: парсер для .json файлов

```python
# parsers/json/json_parser.py
import json
import os
from typing import TYPE_CHECKING

from ..base_parser import BaseParser

if TYPE_CHECKING:
    from contracts import FileSnapshot


class JSONParser(BaseParser):
    """Парсер JSON файлов — извлекает текст из строковых полей."""
    
    def __init__(self):
        super().__init__("json-parser")
    
    def _parse(self, file: 'FileSnapshot') -> str:
        file_path = file.full_path
        
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found | file={file.path}")
        
        self.logger.info(f"Parsing JSON | file={file.path}")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Рекурсивно извлекаем текст из всех строковых полей
        texts = []
        self._extract_strings(data, texts)
        
        content = '\n'.join(texts)
        
        if not content.strip():
            raise ValueError(f"No text content in JSON | file={file.path}")
        
        self.logger.info(f"✅ Parsed JSON | file={file.path} strings={len(texts)}")
        return content
    
    def _extract_strings(self, obj, texts: list):
        """Рекурсивно извлекает строки из JSON структуры."""
        if isinstance(obj, str):
            if obj.strip():
                texts.append(obj)
        elif isinstance(obj, dict):
            for value in obj.values():
                self._extract_strings(value, texts)
        elif isinstance(obj, list):
            for item in obj:
                self._extract_strings(item, texts)
```

## Пример: парсер с OCR

Если ваш формат содержит изображения и требует OCR:

```python
from ..word.ocr_processor import process_images_with_ocr

class ImageDocParser(BaseParser):
    def __init__(self, enable_ocr: bool = True):
        super().__init__("imagedoc-parser")
        self.enable_ocr = enable_ocr
    
    def _parse(self, file: 'FileSnapshot') -> str:
        # ... извлечение изображений ...
        
        if self.enable_ocr and images:
            ocr_text = process_images_with_ocr(images)
            content += "\n\n" + ocr_text
        
        return content
```

## Тестирование

```python
from contracts import FileSnapshot
from parsers.xyz.xyz_parser import XYZParser

parser = XYZParser()

file = FileSnapshot(
    hash="test123",
    path="test.xyz",
    full_path="/tmp/test.xyz"
)

# Создайте тестовый файл
with open("/tmp/test.xyz", "w") as f:
    f.write("Test content")

text = parser.parse(file)
print(f"Extracted: {text}")
```

## Отладка

Если парсер не работает:

1. Проверьте, что расширение добавлено в `build_parser_registry()`
2. Проверьте импорт в `parsers/__init__.py`
3. Проверьте зависимости в `requirements.txt`
4. Пересоберите Docker-образ
5. Проверьте логи: `docker logs alpaca-ingest-1 2>&1 | grep xyz-parser`

## Чек-лист

- [ ] Создана папка `parsers/xyz/`
- [ ] Создан файл `xyz_parser.py` с классом `XYZParser`
- [ ] Создан файл `__init__.py` с экспортом
- [ ] Добавлен импорт в `parsers/__init__.py`
- [ ] Добавлено расширение в `build_parser_registry()`
- [ ] Добавлены зависимости в `requirements.txt` (если нужны)
- [ ] Пересобран Docker-образ
- [ ] Протестирован парсинг файла
