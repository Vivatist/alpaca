"""
Тестовый набор для complex_agent backend.

Содержит реальные запросы, использованные при разработке и отладке.
Запуск: pytest tests/test_complex_agent_queries.py -v
"""

import pytest
from typing import List, Dict, Any

# Тестовые запросы с ожидаемыми фильтрами и результатами
TEST_QUERIES = [
    # === Базовые запросы по категории ===
    {
        "query": "Найди договоры подряда",
        "expected_filters": {
            "category": "Договор подряда",
        },
        "description": "Поиск по категории",
    },
    
    # === Поиск по entity (компания) ===
    {
        "query": "Найди договоры с Акпан",
        "expected_filters": {
            "entity": "Акпан",
        },
        "should_find_entity": "Акпан",
        "description": "Entity: название компании",
    },
    {
        "query": "Найди все договора с АкпанОМ",
        "expected_filters": {
            "entity": "Акпан",  # Должно быть нормализовано
        },
        "should_find_entity": "Акпан",
        "description": "Entity: склонённое название → нормализация",
    },
    {
        "query": "Найди документы компании ТОО Акпан",
        "expected_filters": {
            "entity": "Акпан",  # или "ТОО Акпан"
        },
        "should_find_entity": "Акпан",
        "description": "Entity: с организационной формой",
    },
    
    # === Поиск по entity (ФИО) ===
    {
        "query": "Кто директор Акпана?",
        "expected_filters": {
            "entity": "Акпан",
        },
        "expected_answer_contains": "Душекенов",
        "description": "Entity: вопрос о персоне в компании",
    },
    {
        "query": "Что ты знаешь про Душекенова?",
        "expected_filters": {
            "entity": "Душекенов",
        },
        "should_find_entity": "Душекенов",
        "description": "Entity: поиск по фамилии (гибридный поиск)",
    },
    
    # === Поиск по дате ===
    {
        "query": "Документы за 2024 год",
        "expected_filters": {
            "date_from": "2024-01-01",
            "date_to": "2024-12-31",
        },
        "description": "Date: год полностью",
    },
    {
        "query": "Найди договор акпана весна 2024 год",
        "expected_filters": {
            "entity": "Акпан",
            "date_from": "2024-03-01",
            "date_to": "2024-05-31",
        },
        "description": "Entity + Date: сезон (весна)",
    },
    
    # === Комбинированные запросы ===
    {
        "query": "Договоры подряда с Акпан за 2024",
        "expected_filters": {
            "category": "Договор подряда",
            "entity": "Акпан",
            "date_from": "2024-01-01",
            "date_to": "2024-12-31",
        },
        "description": "Category + Entity + Date",
    },
    
    # === Запросы с keywords ===
    {
        "query": "Найди акты выполненных работ",
        "expected_filters": {
            "category": "Акт выполненных работ",
        },
        "description": "Category: акты",
    },
    {
        "query": "Техническая документация по проекту",
        "expected_filters": {
            "category": "Техническая документация",
            "keywords": ["проект"],
        },
        "description": "Category + Keywords",
    },
    
    # === Жизненные ситуации: юридические вопросы ===
    {
        "query": "Какие штрафные санкции предусмотрены в договорах?",
        "expected_filters": {
            "keywords": ["штраф", "санкции", "пени"],
        },
        "description": "Юрист: поиск штрафных санкций",
    },
    {
        "query": "Покажи все доверенности, выданные в этом году",
        "expected_filters": {
            "category": "Доверенность",
            "date_from": "2025-01-01",
            "date_to": "2025-12-31",
        },
        "description": "Юрист: актуальные доверенности",
    },
    {
        "query": "Найди договоры со сроком действия до конца года",
        "expected_filters": {
            "keywords": ["срок", "действие"],
        },
        "description": "Юрист: истекающие договоры",
    },
    
    # === Жизненные ситуации: бухгалтерия ===
    {
        "query": "Счета-фактуры за последний квартал",
        "expected_filters": {
            "category": "Счет-фактура, счет",
            "date_from": "2025-10-01",
            "date_to": "2025-12-31",
        },
        "description": "Бухгалтер: счета за квартал",
    },
    {
        "query": "На какую сумму заключен договор с Акпаном?",
        "expected_filters": {
            "entity": "Акпан",
            "keywords": ["сумма", "стоимость", "цена"],
        },
        "expected_answer_contains": "тенге",
        "description": "Бухгалтер: сумма договора",
    },
    {
        "query": "Какие работы выполнены по договору бурения?",
        "expected_filters": {
            "keywords": ["бурение", "работы"],
        },
        "description": "Бухгалтер: объём выполненных работ",
    },
    
    # === Жизненные ситуации: руководитель ===
    {
        "query": "С кем мы работаем по буровым работам?",
        "expected_filters": {
            "keywords": ["бурение", "буровые"],
        },
        "should_find_entity": "Акпан",
        "description": "Директор: контрагенты по направлению",
    },
    {
        "query": "Какие договоры подписаны за последний месяц?",
        "expected_filters": {
            "date_from": "2025-11-10",
            "date_to": "2025-12-10",
        },
        "description": "Директор: новые договоры",
    },
    {
        "query": "Покажи все документы по шахте Тентекская",
        "expected_filters": {
            "keywords": ["Тентекская", "шахта"],
        },
        "description": "Директор: документы по объекту",
    },
    
    # === Жизненные ситуации: менеджер проекта ===
    {
        "query": "Какие дополнительные соглашения есть к договору?",
        "expected_filters": {
            "keywords": ["дополнительное соглашение"],
        },
        "description": "ПМ: допсоглашения",
    },
    {
        "query": "Найди техзадание на буровые работы",
        "expected_filters": {
            "category": "Техническая документация",
            "keywords": ["техзадание", "ТЗ", "бурение"],
        },
        "description": "ПМ: техническое задание",
    },
    {
        "query": "Что указано в акте приёмки работ?",
        "expected_filters": {
            "category": "Акт выполненных работ",
            "keywords": ["приёмка"],
        },
        "description": "ПМ: акт приёмки",
    },
    
    # === Жизненные ситуации: общие вопросы ===
    {
        "query": "Кто подписывает документы от имени Георезонанс?",
        "expected_filters": {
            "entity": "Георезонанс",
        },
        "description": "Общий: подписант компании",
    },
    {
        "query": "Найди письма от контрагентов",
        "expected_filters": {
            "category": "Письмо",
        },
        "description": "Общий: входящая корреспонденция",
    },
    {
        "query": "Есть ли протоколы совещаний?",
        "expected_filters": {
            "category": "Протокол, меморандум",
        },
        "description": "Общий: протоколы",
    },
    
    # === Сложные запросы с контекстом ===
    {
        "query": "Договор на бурение скважин для дегазации угольного пласта",
        "expected_filters": {
            "category": "Договор подряда",
            "keywords": ["бурение", "скважина", "дегазация"],
        },
        "should_find_entity": "Акпан",
        "description": "Сложный: технический контекст",
    },
    {
        "query": "Документы по плазменно-импульсному воздействию",
        "expected_filters": {
            "keywords": ["плазменно-импульсное", "ПИВ"],
        },
        "description": "Сложный: специфичная технология",
    },
    {
        "query": "Все документы Карагандинской области",
        "expected_filters": {
            "keywords": ["Караганда", "Карагандинская"],
        },
        "description": "Сложный: географический фильтр",
    },
]


class TestQueryExtraction:
    """Тесты для LLM extraction фильтров из запроса."""
    
    @pytest.mark.parametrize("test_case", TEST_QUERIES, ids=[t["description"] for t in TEST_QUERIES])
    def test_filter_extraction(self, test_case: Dict[str, Any], complex_agent_backend):
        """
        Проверяет, что LLM правильно извлекает фильтры из запроса.
        
        Требует fixture complex_agent_backend с методом extract_filters(query).
        """
        query = test_case["query"]
        expected = test_case.get("expected_filters", {})
        
        # Извлекаем фильтры
        filters = complex_agent_backend.extract_filters(query)
        
        # Проверяем основные поля
        if "category" in expected:
            assert filters.category == expected["category"], \
                f"Category mismatch: expected '{expected['category']}', got '{filters.category}'"
        
        if "entity" in expected:
            # Entity может быть с вариациями (Акпан, ТОО Акпан)
            assert expected["entity"].lower() in (filters.entity or "").lower(), \
                f"Entity mismatch: expected '{expected['entity']}' in '{filters.entity}'"
        
        if "date_from" in expected:
            assert str(filters.date_from) == expected["date_from"], \
                f"date_from mismatch: expected '{expected['date_from']}', got '{filters.date_from}'"
        
        if "date_to" in expected:
            assert str(filters.date_to) == expected["date_to"], \
                f"date_to mismatch: expected '{expected['date_to']}', got '{filters.date_to}'"


class TestSearch:
    """Тесты поиска документов."""
    
    @pytest.mark.parametrize("test_case", [t for t in TEST_QUERIES if "should_find_entity" in t], 
                             ids=[t["description"] for t in TEST_QUERIES if "should_find_entity" in t])
    def test_entity_search(self, test_case: Dict[str, Any], complex_agent_backend):
        """
        Проверяет, что гибридный поиск находит документы с указанным entity.
        """
        query = test_case["query"]
        expected_entity = test_case["should_find_entity"]
        
        # Выполняем поиск
        results, _ = complex_agent_backend.search(query, stream_callback=None)
        
        # Проверяем, что хотя бы один результат содержит entity
        found_entity = False
        for result in results:
            # Проверяем в entities metadata
            if result.metadata and result.metadata.entities:
                for entity in result.metadata.entities:
                    if expected_entity.lower() in entity.get("name", "").lower():
                        found_entity = True
                        break
            
            # Проверяем в content
            if expected_entity.lower() in result.content.lower():
                found_entity = True
                break
        
        assert found_entity, \
            f"Entity '{expected_entity}' not found in results for query '{query}'"


class TestEndToEnd:
    """End-to-end тесты RAG pipeline."""
    
    @pytest.mark.parametrize("test_case", [t for t in TEST_QUERIES if "expected_answer_contains" in t],
                             ids=[t["description"] for t in TEST_QUERIES if "expected_answer_contains" in t])
    def test_answer_quality(self, test_case: Dict[str, Any], complex_agent_backend):
        """
        Проверяет, что финальный ответ LLM содержит ожидаемую информацию.
        """
        query = test_case["query"]
        expected_in_answer = test_case["expected_answer_contains"]
        
        # Выполняем полный RAG pipeline
        answer = complex_agent_backend.chat(query, stream_callback=None)
        
        assert expected_in_answer.lower() in answer.lower(), \
            f"Expected '{expected_in_answer}' in answer, got: {answer[:200]}..."


# === Fixtures ===

@pytest.fixture
def complex_agent_backend():
    """
    Создаёт экземпляр ComplexAgentBackend.
    
    Требует:
    - Запущенный Ollama с моделями
    - Подключение к PostgreSQL с данными
    """
    pytest.skip("Requires running services and real data")
    
    # Раскомментировать для интеграционных тестов:
    # from backends.complex_agent import ComplexAgentBackend
    # return ComplexAgentBackend()


# === Manual test runner ===

if __name__ == "__main__":
    """
    Запуск вручную для проверки запросов.
    
    Использование:
        cd services/chat_backend
        python -m tests.test_complex_agent_queries
    """
    import sys
    sys.path.insert(0, "src")
    
    from backends.complex_agent import ComplexAgentBackend
    
    backend = ComplexAgentBackend()
    
    print("=" * 60)
    print("COMPLEX AGENT TEST SUITE")
    print("=" * 60)
    
    for i, test_case in enumerate(TEST_QUERIES, 1):
        print(f"\n[{i}/{len(TEST_QUERIES)}] {test_case['description']}")
        print(f"Query: {test_case['query']}")
        
        try:
            # Извлекаем фильтры
            filters = backend._extract_filters(test_case["query"])
            print(f"Filters: {filters.to_dict()}")
            
            # Выполняем поиск
            results, debug = backend._search_with_retry(
                test_case["query"], 
                filters, 
                stream_callback=None
            )
            
            print(f"Results: {len(results)} documents")
            
            if results:
                # Показываем первый результат
                first = results[0]
                print(f"  Top result: {first.metadata.file_path}")
                print(f"  Score: {first.final_score:.3f}")
                print(f"  Content preview: {first.content[:100]}...")
            
            # Проверяем expected_entity
            if "should_find_entity" in test_case:
                expected = test_case["should_find_entity"]
                found = any(
                    expected.lower() in r.content.lower() or
                    any(expected.lower() in e.get("name", "").lower() 
                        for e in (r.metadata.entities or []))
                    for r in results
                )
                status = "✅" if found else "❌"
                print(f"{status} Entity '{expected}' found: {found}")
            
        except Exception as e:
            print(f"❌ Error: {e}")
        
        print("-" * 40)
