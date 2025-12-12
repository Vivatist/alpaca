# Создание нового Reranker

Реранкеры используют **Protocol + Registry** паттерн. Для добавления нового реранкера:

## 1. Создать файл реранкера

```
services/chat_backend/src/rerankers/
├── protocol.py          # Базовый протокол (не трогать)
├── none.py              # Pass-through реранкер
├── date.py              # Сортировка по дате
├── myreranker.py        # ← Новый реранкер
└── __init__.py          # Registry
```

## 2. Реализовать протокол Reranker (`myreranker.py`)

```python
from typing import List

from logging_config import get_logger

from .protocol import Reranker, RerankItem, RerankResult

logger = get_logger("chat_backend.reranker.myreranker")


class MyReranker(Reranker):
    """
    Мой кастомный реранкер.
    
    Описание логики реранкинга...
    Параметры задаются внутри класса, НЕ через ENV.
    """
    
    # Параметры реранкера — значения по умолчанию здесь
    DEFAULT_TOP_K = 5      # Отсечение: вернуть только top 5
    DEFAULT_WEIGHT = 0.5   # Вес параметра
    
    def __init__(self, weight: float | None = None, top_k: int | None = None):
        """
        Args:
            weight: Вес параметра. None = DEFAULT_WEIGHT
            top_k: Максимум результатов. None = DEFAULT_TOP_K
        """
        self.weight = weight if weight is not None else self.DEFAULT_WEIGHT
        self.top_k = top_k if top_k is not None else self.DEFAULT_TOP_K
        logger.info(f"✅ MyReranker initialized | weight={self.weight} top_k={self.top_k}")
    
    @property
    def name(self) -> str:
        return "myreranker"
    
    def rerank(
        self, 
        query: str, 
        items: List[RerankItem],
        top_k: int | None = None
    ) -> List[RerankResult]:
        """
        Переранжировать результаты поиска.
        
        Args:
            query: Запрос пользователя (может использоваться для семантического реранкинга)
            items: Список элементов для реранкинга
            top_k: Ограничение из вызова (приоритет над self.top_k)
            
        Returns:
            Список RerankResult, отсортированный по rerank_score (убывание)
        """
        if not items:
            return []
        
        results = []
        for item in items:
            # Вычисляем новый score
            rerank_score = self._calculate_score(query, item)
            
            results.append(RerankResult(
                content=item.content,
                metadata=item.metadata,
                similarity=item.similarity,  # Оригинальный score
                rerank_score=rerank_score     # Новый score
            ))
        
        # Сортируем по rerank_score (убывание)
        results.sort(key=lambda x: x.rerank_score, reverse=True)
        
        # Ограничиваем top_k (self.top_k если не передан)
        effective_top_k = top_k if top_k is not None else self.top_k
        if effective_top_k is not None:
            results = results[:effective_top_k]
        
        logger.debug(f"🔄 MyReranker: {len(items)} → {len(results)} items | top_k={effective_top_k}")
        
        return results
    
    def _calculate_score(self, query: str, item: RerankItem) -> float:
        """Вычислить rerank_score для элемента."""
        # Ваша логика здесь
        return item.similarity * self.weight
```

## 3. Зарегистрировать в реестре (`__init__.py`)

```python
from .protocol import Reranker, RerankItem, RerankResult
from .none import NoneReranker
from .date import DateReranker
from .myreranker import MyReranker  # Добавить импорт

RERANKERS: dict[str, Type[Reranker]] = {
    "none": NoneReranker,
    "date": DateReranker,
    "myreranker": MyReranker,  # Добавить в реестр
}
```

## 4. Добавить ENV в `docker-compose.yml`

```yaml
chat-backend:
  environment:
    - RERANKER_TYPE=myreranker  # Включить новый реранкер
```

**Важно**: Параметры реранкера (веса и т.д.) задаются внутри класса, 
НЕ через ENV. Если нужны настраиваемые параметры — добавьте их 
как константы класса с дефолтными значениями.

---

## Справка по типам

### RerankItem (вход)

```python
@dataclass
class RerankItem:
    content: str           # Текст чанка
    metadata: Dict[str, Any]  # Метаданные (file_path, modified_at, title, etc.)
    similarity: float      # Оригинальный score от vector search (0-1)
```

### RerankResult (выход)

```python
@dataclass
class RerankResult:
    content: str           # Текст чанка
    metadata: Dict[str, Any]  # Метаданные
    similarity: float      # Оригинальный score
    rerank_score: float    # Новый score после реранкинга (0-1)
    
    def to_item(self) -> RerankItem:
        """Конвертировать в RerankItem для передачи следующему реранкеру."""
        ...
```

### results_to_items (хелпер для цепочки)

```python
from rerankers import results_to_items

# Конвертирует List[RerankResult] → List[RerankItem]
# rerank_score становится новым similarity
items2 = results_to_items(results1)
```

---

## Соединение реранкеров в цепочку

Реранкеры можно соединять последовательно. Используйте `results_to_items()`:

```python
from rerankers import DateReranker, ExtensionReranker, results_to_items

# 1. Сначала сортировка по дате (без отсечения)
date_reranker = DateReranker()  # top_k=None
date_results = date_reranker.rerank(query, items)

# 2. Затем фильтрация по расширению (с отсечением)
ext_reranker = ExtensionReranker()  # top_k=5
final_results = ext_reranker.rerank(query, results_to_items(date_results))

# final_results: отсортированы по дате → отфильтрованы по расширению → top 5
```

**Важно**: `rerank_score` первого реранкера становится `similarity` для второго.

---

## Существующие реранкеры

| Реранкер | ENV | DEFAULT_TOP_K | Описание |
|----------|-----|---------------|----------|
| `none` | `RERANKER_TYPE=none` | None | Pass-through, без изменений |
| `date` | `RERANKER_TYPE=date` | None | Сортировка по дате (weight=0.5) |
| `extension` | `RERANKER_TYPE=extension` | 5 | Приоритет по типу документа (weight=0.3) |

**Примечание**: `DEFAULT_TOP_K=None` означает без отсечения (все результаты).
Для реранкеров с отсечением установите `DEFAULT_TOP_K=5` (или другое значение).

---

## Примеры реранкеров

### Семантический реранкер (Cross-Encoder)

```python
class CrossEncoderReranker(Reranker):
    """Реранкинг через cross-encoder модель."""
    
    DEFAULT_TOP_K = 5  # Отсечение после реранкинга
    
    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2", top_k: int | None = None):
        from sentence_transformers import CrossEncoder
        self.model = CrossEncoder(model_name)
        self.top_k = top_k if top_k is not None else self.DEFAULT_TOP_K
    
    def rerank(self, query: str, items: List[RerankItem], top_k: int | None = None):
        pairs = [(query, item.content) for item in items]
        scores = self.model.predict(pairs)
        # ... формируем RerankResult с новыми scores
        # ... отсекаем по effective_top_k
```

### Комбинированный реранкер

```python
class CombinedReranker(Reranker):
    """Комбинация нескольких реранкеров."""
    
    def __init__(self, rerankers: List[Reranker], weights: List[float]):
        self.rerankers = rerankers
        self.weights = weights
    
    def rerank(self, query: str, items: List[RerankItem], top_k: int | None = None):
        # Применяем каждый реранкер, комбинируем scores
        ...
```
