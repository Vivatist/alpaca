# ALPACA RAG - Постепенная миграция

## Текущая структура

```
alpaca/
├── settings.py          # ✅ Настройки
├── .env                 # ✅ Конфигурация
├── docker/              # ✅ Внешние сервисы
│   └── docker-compose.yml
├── venv/                # ✅ Python окружение
├── app/
│   ├── core/            # Пусто - будем добавлять
│   ├── db/              # Пусто - будем добавлять
│   └── utils/
└── tests/               # Пусто - будем добавлять
```

## План миграции

### Шаг 1: File Watcher (текущий)
- [ ] Портировать file_watcher.py из старого проекта
- [ ] Создать тесты test_file_watcher.py
- [ ] Запустить и отладить

### Шаг 2: Database
- [ ] connection.py - подключение к PostgreSQL
- [ ] Создание таблицы documents
- [ ] Тесты

### Шаг 3: Document Parser
- [ ] parser.py для Unstructured API
- [ ] Тесты парсинга разных форматов

### Шаг 4: Processing Pipeline
- [ ] Чанкирование
- [ ] Embeddings
- [ ] Сохранение в БД

## Старый проект

Расположение: `/home/alpaca/alpaca-n8n/`

## Следующий шаг

Какой компонент портируем первым?
