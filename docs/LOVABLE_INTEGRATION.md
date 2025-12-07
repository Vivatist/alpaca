# Интеграция с Lovable.dev

## Обзор

Lovable.dev — это AI-powered платформа для создания веб-приложений. Мы используем её для создания фронтенда чат-интерфейса ALPACA.

## API Endpoints

**Base URL**: `https://api.alpaca-smart.com:8443/chat`

### 1. Отправка сообщения (JSON)

```
POST /api/chat
Content-Type: application/json

{
  "message": "Ваш вопрос",
  "conversation_id": "uuid (опционально)"
}
```

**Ответ:**
```json
{
  "answer": "Текст ответа от AI...",
  "conversation_id": "550e8400-e29b-41d4-a716-446655440000",
  "sources": [
    {
      "file_path": "Папка/Документ.docx",
      "file_name": "Документ.docx",
      "chunk_index": 15,
      "similarity": 0.66,
      "download_url": "https://api.alpaca-smart.com:8443/chat/api/files/download?path=..."
    }
  ]
}
```

### 2. Отправка сообщения с файлом (multipart/form-data)

```
POST /api/chat/with-file
Content-Type: multipart/form-data

message: "Ваш вопрос"
conversation_id: "uuid (опционально)"
file: <файл>
```

**Ответ:** такой же + поле `attachment`:
```json
{
  "answer": "...",
  "conversation_id": "...",
  "sources": [...],
  "attachment": {
    "filename": "uploaded.docx",
    "size": 12345,
    "content_type": "application/vnd.openxmlformats..."
  }
}
```

### 3. Статистика базы знаний

```
GET /api/chat/stats
```

**Ответ:**
```json
{
  "total_chunks": 1234,
  "unique_files": 56
}
```

### 4. Скачивание файла

```
GET /api/files/download?path={encoded_path}
```

Возвращает файл для скачивания.

### 5. Информация о файле

```
GET /api/files/preview?path={encoded_path}
```

**Ответ:**
```json
{
  "name": "Устав.docx",
  "path": "Компания/Устав.docx",
  "size": 45678,
  "size_human": "44.6 KB",
  "extension": ".docx",
  "exists": true
}
```

## Работа в Lovable.dev

### Шаг 1: Создание проекта

1. Зайдите на https://lovable.dev
2. Создайте новый проект
3. Скопируйте промпт из файла `LOVABLE_PROMPT.md`
4. Вставьте в чат Lovable и дождитесь генерации

### Шаг 2: Подключение API

После генерации приложения нужно убедиться, что API URL правильно настроен.

**Вариант 1: Константа в коде**

Найдите в сгенерированном коде файл с API вызовами (обычно `src/lib/api.ts` или `src/services/chat.ts`) и проверьте:

```typescript
const API_BASE_URL = "https://api.alpaca-smart.com:8443/chat";
```

**Вариант 2: Переменная окружения**

Если Lovable создал `.env` файл, добавьте:

```env
VITE_API_URL=https://api.alpaca-smart.com:8443/chat
```

И используйте в коде:
```typescript
const API_BASE_URL = import.meta.env.VITE_API_URL || "https://api.alpaca-smart.com:8443/chat";
```

**Пример функции для отправки сообщения:**

```typescript
async function sendMessage(message: string, conversationId?: string) {
  const response = await fetch(`${API_BASE_URL}/api/chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      message,
      conversation_id: conversationId,
    }),
  });
  
  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }
  
  return await response.json();
}
```

**Пример функции для отправки с файлом:**

```typescript
async function sendMessageWithFile(message: string, file?: File, conversationId?: string) {
  const formData = new FormData();
  formData.append('message', message);
  
  if (conversationId) {
    formData.append('conversation_id', conversationId);
  }
  
  if (file) {
    formData.append('file', file);
  }
  
  const response = await fetch(`${API_BASE_URL}/api/chat/with-file`, {
    method: 'POST',
    body: formData,
    // НЕ устанавливайте Content-Type — браузер сделает это автоматически с boundary
  });
  
  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }
  
  return await response.json();
}
```

### Шаг 3: Настройка CORS (если нужно)

API уже настроен с `allow_origins=["*"]`, так что CORS проблем быть не должно.

Если всё же возникают ошибки CORS, проверьте:
- Правильность URL (https, порт 8443)
- Что запрос идёт на `/chat/api/...` а не просто `/api/...`

### Шаг 4: Тестирование

1. После генерации приложения протестируйте отправку сообщений
2. Проверьте отображение источников
3. Проверьте скачивание файлов
4. Протестируйте загрузку файлов через скрепку

## Структура ответа для фронтенда

```typescript
interface ChatResponse {
  answer: string;           // Текст ответа (может содержать markdown)
  conversation_id: string;  // UUID для продолжения диалога
  sources: Source[];        // Массив источников
  attachment?: Attachment;  // Информация о загруженном файле (если был)
}

interface Source {
  file_path: string;      // Полный путь к файлу
  file_name: string;      // Имя файла
  chunk_index: number;    // Индекс чанка в документе
  similarity: number;     // Релевантность (0-1)
  download_url: string;   // URL для скачивания
}

interface Attachment {
  filename: string;       // Имя загруженного файла
  size: number;          // Размер в байтах
  content_type: string;  // MIME тип
}
```

## Обработка ошибок

| Код | Описание |
|-----|----------|
| 200 | Успех |
| 413 | Файл слишком большой (макс. 10 MB) |
| 500 | Внутренняя ошибка сервера |

## Советы

1. **Таймауты**: LLM может отвечать до 30-60 секунд, установите соответствующий таймаут
2. **Markdown**: Ответы могут содержать markdown, используйте библиотеку для рендеринга
3. **conversation_id**: Сохраняйте и передавайте для продолжения диалога
4. **sources**: Могут быть дубликаты файлов с разными chunk_index — группируйте по file_path
