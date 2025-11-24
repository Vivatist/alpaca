# Admin Backend

FastAPI бэкенд для управления и мониторинга системы Alpaca N8N.

## Возможности

- 📊 **Мониторинг** - статистика обработки файлов в реальном времени
- 🔍 **Детальная информация** - просмотр файлов, очередей, ошибок
- ⚙️ **Конфигурация** - получение настроек всех сервисов
- 🏥 **Health Checks** - проверка состояния системы
- 📚 **Автодокументация** - Swagger UI и ReDoc

## API Endpoints

### Health
- `GET /` - Проверка доступности
- `GET /health` - Комплексная проверка системы

### File State
- `GET /api/file-state/stats` - Статистика по статусам файлов
- `GET /api/file-state/files` - Список файлов с фильтрацией и пагинацией
- `GET /api/file-state/queue` - Текущая очередь обработки
- `GET /api/file-state/errors` - Файлы с ошибками

### Documents
- `GET /api/documents/stats` - Статистика по векторной БД

### Configuration
- `GET /api/config/file-watcher` - Переменные окружения file-watcher
- `GET /api/config/main-loop` - Переменные окружения main-loop

### Dashboard
- `GET /api/dashboard` - Все данные для дашборда одним запросом

## Документация API

После запуска доступна по адресам:
- **Swagger UI**: http://localhost:8080/docs
- **ReDoc**: http://localhost:8080/redoc
- **OpenAPI JSON**: http://localhost:8080/openapi.json

## Запуск

```bash
docker compose up -d admin-backend
```

## Использование

### Curl
```bash
# Статистика файлов
curl http://localhost:8080/api/file-state/stats

# Список файлов со статусом 'added'
curl "http://localhost:8080/api/file-state/files?status=added&limit=10"

# Очередь обработки
curl http://localhost:8080/api/file-state/queue

# Конфигурация file-watcher
curl http://localhost:8080/api/config/file-watcher
```

### Python
```python
import requests

# Получить статистику
response = requests.get('http://localhost:8080/api/file-state/stats')
stats = response.json()
print(f"Всего файлов: {stats['total']}")
print(f"Ожидают обработки: {stats['added'] + stats['updated']}")
```

### JavaScript (Lovable.dev)
```javascript
// Получить данные для дашборда
const response = await fetch('http://localhost:8080/api/dashboard');
const data = await response.json();

console.log('File State:', data.file_state);
console.log('Documents:', data.documents);
console.log('Queue:', data.queue);
```

## Интеграция с Lovable.dev

1. **Импорт OpenAPI спецификации**:
   ```
   http://localhost:8080/openapi.json
   ```

2. **Автогенерация клиента**:
   Lovable автоматически создаст типизированный клиент на основе OpenAPI

3. **Использование в UI**:
   ```typescript
   import { AlpacaAdminAPI } from './generated/api';
   
   const api = new AlpacaAdminAPI({ baseUrl: 'http://localhost:8080' });
   const stats = await api.getFileStateStats();
   ```

## CORS

По умолчанию разрешены запросы с любых доменов (`allow_origins=["*"]`).

В продакшене укажите конкретные домены в `main.py`:
```python
allow_origins=["https://your-lovable-app.dev"]
```

## Переменные окружения

```env
POSTGRES_HOST=supabase-db
POSTGRES_PORT=5432
POSTGRES_DB=postgres
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
```

## Разработка

### Локальный запуск
```bash
cd admin-backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8080
```

### Добавление нового эндпоинта

1. Добавьте метод в `database.py`:
```python
def get_new_data(self) -> Dict:
    with self.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM table")
            return cur.fetchall()
```

2. Добавьте эндпоинт в `main.py`:
```python
@app.get("/api/new-endpoint", tags=["Custom"])
async def new_endpoint():
    """Описание эндпоинта"""
    return db.get_new_data()
```

3. Документация обновится автоматически!

## Troubleshooting

### Ошибка подключения к БД
```bash
docker exec admin-backend python -c "from database import Database; db = Database(); print(db.get_database_health())"
```

### Проверка логов
```bash
docker logs admin-backend --tail 50
```

### Проверка доступности
```bash
curl http://localhost:8080/health
```
