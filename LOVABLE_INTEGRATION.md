# Интеграция с Lovable.dev

## Шаг 1: Admin Backend готов ✅

FastAPI backend запущен на порту **8080** с полной OpenAPI документацией.

### Доступные эндпоинты:

**Swagger UI**: http://localhost:8080/docs  
**ReDoc**: http://localhost:8080/redoc  
**OpenAPI JSON**: http://localhost:8080/openapi.json

## Шаг 2: Настройка Cloudflare Tunnel

### Установка cloudflared

```bash
# Debian/Ubuntu
wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
sudo dpkg -i cloudflared-linux-amd64.deb

# Или через Docker
docker run cloudflare/cloudflared:latest tunnel --help
```

### Создание туннеля

```bash
# 1. Авторизация в Cloudflare
cloudflared tunnel login

# 2. Создание туннеля
cloudflared tunnel create alpaca-admin

# 3. Конфигурация (создать ~/.cloudflared/config.yml)
cat > ~/.cloudflared/config.yml << EOF
tunnel: <TUNNEL_ID>
credentials-file: /root/.cloudflared/<TUNNEL_ID>.json

ingress:
  - hostname: alpaca-admin.your-domain.com
    service: http://localhost:8080
  - service: http_status:404
EOF

# 4. DNS маршрутизация
cloudflared tunnel route dns alpaca-admin alpaca-admin.your-domain.com

# 5. Запуск туннеля
cloudflared tunnel run alpaca-admin
```

### Или через Docker Compose

Добавьте в `docker-compose.yml`:

```yaml
  cloudflare-tunnel:
    image: cloudflare/cloudflared:latest
    container_name: alpaca-cloudflare-tunnel
    restart: unless-stopped
    command: tunnel --no-autoupdate run
    environment:
      - TUNNEL_TOKEN=<YOUR_TUNNEL_TOKEN>
    networks:
      - alpaca_network
    depends_on:
      - admin-backend
```

## Шаг 3: Интеграция с Lovable.dev

### Вариант 1: Импорт OpenAPI спецификации

1. Откройте Lovable.dev проект
2. Перейдите в настройки интеграций
3. Добавьте API:
   ```
   URL: https://alpaca-admin.your-domain.com/openapi.json
   Type: OpenAPI 3.0
   ```
4. Lovable автоматически сгенерирует типизированный клиент

### Вариант 2: Ручная настройка

```typescript
// lib/api.ts
const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'https://alpaca-admin.your-domain.com';

export async function getFileStateStats() {
  const response = await fetch(`${API_BASE}/api/file-state/stats`);
  return response.json();
}

export async function getDashboardData() {
  const response = await fetch(`${API_BASE}/api/dashboard`);
  return response.json();
}
```

### Вариант 3: Автогенерация клиента

```bash
# Установка генератора
npm install @openapitools/openapi-generator-cli -g

# Генерация TypeScript клиента
openapi-generator-cli generate \
  -i https://alpaca-admin.your-domain.com/openapi.json \
  -g typescript-fetch \
  -o ./src/generated/api

# Использование
import { DefaultApi } from './generated/api';

const api = new DefaultApi({
  basePath: 'https://alpaca-admin.your-domain.com'
});

const stats = await api.apiFileStateStatsGet();
```

## Шаг 4: Пример UI компонента для Lovable

```tsx
// components/Dashboard.tsx
import { useEffect, useState } from 'react';

interface DashboardData {
  file_state: {
    total: number;
    ok: number;
    added: number;
    updated: number;
    processed: number;
    error: number;
  };
  documents: {
    total_chunks: number;
    unique_files: number;
    avg_chunks_per_file: number;
  };
}

export function Dashboard() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchData() {
      try {
        const response = await fetch('https://alpaca-admin.your-domain.com/api/dashboard');
        const json = await response.json();
        setData(json);
      } catch (error) {
        console.error('Failed to fetch dashboard data:', error);
      } finally {
        setLoading(false);
      }
    }

    fetchData();
    const interval = setInterval(fetchData, 5000); // Обновление каждые 5 секунд

    return () => clearInterval(interval);
  }, []);

  if (loading) return <div>Loading...</div>;
  if (!data) return <div>Error loading data</div>;

  return (
    <div className="dashboard">
      <h1>Alpaca N8N Admin</h1>
      
      <div className="stats-grid">
        <div className="stat-card">
          <h2>File State</h2>
          <div className="stat-value">{data.file_state.total}</div>
          <div className="stat-label">Total Files</div>
          <div className="stat-breakdown">
            <span>✓ OK: {data.file_state.ok}</span>
            <span>+ Added: {data.file_state.added}</span>
            <span>↻ Updated: {data.file_state.updated}</span>
            <span>⚠ Errors: {data.file_state.error}</span>
          </div>
        </div>

        <div className="stat-card">
          <h2>Documents</h2>
          <div className="stat-value">{data.documents.unique_files}</div>
          <div className="stat-label">Unique Files</div>
          <div className="stat-breakdown">
            <span>Chunks: {data.documents.total_chunks}</span>
            <span>Avg: {data.documents.avg_chunks_per_file.toFixed(2)}</span>
          </div>
        </div>
      </div>
    </div>
  );
}
```

## Шаг 5: Автоматическая генерация UI в Lovable

1. В Lovable chat введите:
   ```
   Create a dashboard that displays:
   - File processing statistics from GET /api/file-state/stats
   - Document statistics from GET /api/documents/stats
   - Real-time queue status from GET /api/file-state/queue
   - Error list from GET /api/file-state/errors
   
   API base URL: https://alpaca-admin.your-domain.com
   Use the OpenAPI spec at /openapi.json for type safety
   Add auto-refresh every 5 seconds
   Use shadcn/ui components for styling
   ```

2. Lovable автоматически:
   - Проанализирует OpenAPI спецификацию
   - Создаст типизированные функции для всех эндпоинтов
   - Сгенерирует UI компоненты
   - Настроит авто-обновление данных

## Безопасность

### CORS настройка

В `admin-backend/app/main.py` измените:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://your-lovable-app.lovable.dev"],  # Конкретный домен
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
```

### API Authentication (опционально)

```python
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer()

@app.get("/api/protected")
async def protected_endpoint(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    # Проверка токена
    if token != os.getenv("API_TOKEN"):
        raise HTTPException(status_code=401)
    return {"message": "Authorized"}
```

## Мониторинг

```bash
# Логи admin-backend
docker logs -f alpaca-admin-backend

# Проверка здоровья
curl https://alpaca-admin.your-domain.com/health

# Метрики
curl https://alpaca-admin.your-domain.com/api/dashboard
```

## Что дальше?

1. ✅ **Admin Backend готов**
2. ⏳ **Настроить Cloudflare Tunnel** → публичный HTTPS endpoint
3. ⏳ **Импортировать в Lovable** → автогенерация UI
4. ⏳ **Создать дашборд** → визуализация данных
5. ⏳ **Добавить управление** → эндпоинты для изменения конфигурации

### Следующие фичи для добавления:

- `POST /api/file-state/reset-errors` - сброс статуса error файлов
- `POST /api/file-state/reprocess` - переобработка конкретных файлов
- `GET /api/logs/file-watcher` - стриминг логов
- `GET /api/logs/main-loop` - стриминг логов
- `POST /api/config/update` - обновление конфигурации на лету
- WebSocket для real-time обновлений
