# Как добавить новый Cleaner

## Структура модуля cleaners

```
cleaners/
├── __init__.py      ← реестр + build_cleaner() + pipeline
├── simple.py        ← simple_cleaner()
├── stamps.py        ← stamps_cleaner()
└── your_cleaner.py  ← ваш новый клинер
```

## Шаги

### 1. Создайте файл с клинером

Создайте новый файл, например `my_cleaner.py`:

```python
"""
Описание: что делает этот клинер.
"""
import re


def my_cleaner(text: str) -> str:
    """
    Краткое описание функции.
    
    Args:
        text: Входной текст для очистки
        
    Returns:
        Очищенный текст
    """
    # Ваша логика очистки
    result = text
    
    # Пример: удаление определённого паттерна
    result = re.sub(r'паттерн_для_удаления', '', result)
    
    return result
```

### 2. Зарегистрируйте клинер в `__init__.py`

Добавьте импорт и запись в реестр:

```python
# В начале файла добавьте импорт
from .my_cleaner import my_cleaner

# В словарь CLEANERS добавьте запись
CLEANERS: dict[str, Cleaner] = {
    "simple": simple_cleaner,
    "stamps": stamps_cleaner,
    "my_cleaner": my_cleaner,  # ← новый клинер
}
```

### 3. Добавьте клинер в пайплайн

В `docker-compose.yml` добавьте имя клинера в переменную `CLEANER_PIPELINE`:

```yaml
environment:
  CLEANER_PIPELINE: "simple,stamps,my_cleaner"
```

## Правила написания клинеров

1. **Сигнатура**: `def cleaner_name(text: str) -> str`
2. **Чистая функция**: не должна иметь побочных эффектов
3. **Идемпотентность**: повторный вызов не должен менять результат
4. **Порядок важен**: клинеры применяются последовательно слева направо
5. **Не удаляйте контент**: клинеры должны убирать мусор, а не полезный текст

## Тестирование

Протестируйте клинер локально перед добавлением:

```python
from cleaners.my_cleaner import my_cleaner

test_text = "Текст с мусором для удаления"
result = my_cleaner(test_text)
print(result)
```

## Пример: клинер для удаления водяных знаков

```python
# watermark.py
"""
Удаляет водяные знаки типа "CONFIDENTIAL", "DRAFT" и т.д.
"""
import re


def watermark_cleaner(text: str) -> str:
    """Удаляет распространённые водяные знаки из текста."""
    patterns = [
        r'\b(CONFIDENTIAL|КОНФИДЕНЦИАЛЬНО)\b',
        r'\b(DRAFT|ЧЕРНОВИК)\b',
        r'\b(COPY|КОПИЯ)\b',
    ]
    
    result = text
    for pattern in patterns:
        result = re.sub(pattern, '', result, flags=re.IGNORECASE)
    
    return result
```

## Отладка

Если клинер не работает:

1. Проверьте, что имя в `CLEANERS` совпадает с именем в `CLEANER_PIPELINE`
2. Проверьте импорт в `__init__.py`
3. Пространство имён:  клинер должен быть доступен как `from cleaners import my_cleaner`
4. Пространство имён:  клинер должен быть доступен как `from cleaners import CLEANERS['my_cleaner']`
