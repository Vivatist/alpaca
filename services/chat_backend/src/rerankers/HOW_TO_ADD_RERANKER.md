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
    DEFAULT_WEIGHT = 0.5
    
    def __init__(self, weight: float = DEFAULT_WEIGHT):
        """
        Args:
            weight: Вес параметра (значение по умолчанию в классе)
        """
        self.weight = weight
        logger.info(f"✅ MyReranker initialized | weight={self.weight}")
    
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
            top_k: Ограничение количества результатов (None = все)
            
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
        
        # Ограничиваем top_k
        if top_k is not None:
            results = results[:top_k]
        
        logger.debug(f"🔄 MyReranker: {len(items)} → {len(results)} items")
        
        return results
    
    def _calculate_score(self, query: str, item: RerankItem) -> float:
        """Вычислить rerank_score для элемента."""
        # Ваша логика здесь
        return item.similarity * self.my_param
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
```

---

## Существующие реранкеры

| Реранкер | ENV | Описание |
|----------|-----|----------|
| `none` | `RERANKER_TYPE=none` | Pass-through, без изменений (rerank_score = similarity) |
| `date` | `RERANKER_TYPE=date` | Сортировка по дате модификации (RERANKER_WEIGHT) |

---

## Примеры реранкеров

### Семантический реранкер (Cross-Encoder)

```python
class CrossEncoderReranker(Reranker):
    """Реранкинг через cross-encoder модель."""
    
    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        from sentence_transformers import CrossEncoder
        self.model = CrossEncoder(model_name)
    
    def rerank(self, query: str, items: List[RerankItem], top_k: int | None = None):
        pairs = [(query, item.content) for item in items]
        scores = self.model.predict(pairs)
        # ... формируем RerankResult с новыми scores
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
