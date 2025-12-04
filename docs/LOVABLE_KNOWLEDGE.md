# ALPACA Chat Frontend - Guidelines for Lovable

## Project Overview

This is a chat interface for ALPACA - an enterprise RAG (Retrieval Augmented Generation) system. The frontend connects to a live backend API that searches through company documents and generates AI-powered answers.

## API Configuration

**CRITICAL: The backend API is already running. Always use real API calls, never mock data.**

```
Base URL: https://api.alpaca-smart.com:8443/chat
```

### Endpoints

| Endpoint | Method | Content-Type | Description |
|----------|--------|--------------|-------------|
| `/api/chat` | POST | application/json | Send text message |
| `/api/chat/with-file` | POST | multipart/form-data | Send message with file attachment |
| `/api/chat/stats` | GET | - | Get knowledge base statistics |
| `/api/files/download` | GET | - | Download source file |

### Request/Response Types

```typescript
// POST /api/chat request body
interface ChatRequest {
  message: string;
  conversation_id?: string;  // Include to continue conversation
}

// Response from both /api/chat and /api/chat/with-file
interface ChatResponse {
  answer: string;              // May contain markdown
  conversation_id: string;     // Save and reuse for context
  sources: Source[];           // Documents used for answer
  attachment?: Attachment;     // Only if file was uploaded
}

interface Source {
  file_path: string;           // Full path like "Folder/Doc.docx"
  file_name: string;           // Just filename "Doc.docx"
  chunk_index: number;         // Which part of document
  similarity: number;          // 0-1, relevance score
  download_url: string;        // Direct download link
}

interface Attachment {
  filename: string;
  size: number;                // Bytes
  content_type: string;        // MIME type
}
```

## Coding Style

### TypeScript
- Use strict TypeScript, no `any` types
- Prefer interfaces over types for objects
- Use async/await, not .then() chains

### React
- Functional components only
- Use React hooks (useState, useEffect, useCallback)
- Keep components small and focused

### Styling
- Use Tailwind CSS classes
- Follow mobile-first responsive design
- Use CSS variables for theme colors if needed

### Naming Conventions
- Components: PascalCase (ChatMessage, SourceChip)
- Functions: camelCase (sendMessage, handleSubmit)
- Constants: UPPER_SNAKE_CASE (API_BASE_URL, MAX_FILE_SIZE)
- Files: kebab-case (chat-message.tsx, api-client.ts)

## UI/UX Guidelines

### Current Design (alpaca-insight-chat.lovable.app)

The app uses a clean, centered chat layout:
- **Logo**: ALPACA logo at the top center
- **Chat area**: Centered, max-width container with messages
- **Input**: Bottom-fixed input area with paperclip and send button
- **Hint**: "Shift + Enter для новой строки" below input

### Language
- All UI text must be in **Russian**
- Placeholders, buttons, errors - everything in Russian
- File names from API are often in Cyrillic - handle properly

### Design Tokens (Current Theme)
```
Background: Light/white (#FFFFFF or similar)
Chat container: Centered, comfortable max-width
Messages: Clean bubbles with subtle styling
Input area: Fixed bottom, full-width within container
Accent: Keep existing blue tones
```

### Loading States
- Show spinner/loading indicator while waiting for API
- Disable input and send button during request
- Request timeout: 120 seconds (LLM can be slow)

### Error Handling
- Show user-friendly error messages in Russian
- Provide retry option for failed requests
- Log errors to console for debugging

## Component Requirements

### Layout
- Logo centered at top
- Chat messages in scrollable centered container
- Input area fixed at bottom
- "Shift + Enter для новой строки" hint below input

### ChatMessage
- Support markdown rendering (react-markdown)
- User messages and AI messages clearly distinguished
- Clean, minimal bubble styling

### SourceChips
- Display as small pills/badges below AI response
- Show file icon + filename
- Click to download file
- If many sources, show expandable list

### InputArea
- Paperclip button (📎) for file attachment on the left
- Text input in the center
- Send button on the right
- Support Enter to send, Shift+Enter for new line
- Show attached file as removable chip above input
- Max file size: 10 MB

## File Structure

```
src/
├── components/
│   ├── chat/
│   │   ├── ChatContainer.tsx
│   │   ├── MessageList.tsx
│   │   ├── ChatMessage.tsx
│   │   ├── SourceChips.tsx
│   │   └── LoadingIndicator.tsx
│   ├── input/
│   │   ├── InputArea.tsx
│   │   ├── FileUploadButton.tsx
│   │   └── AttachmentPreview.tsx
│   └── ui/
│       ├── Button.tsx
│       ├── Toast.tsx
│       └── Spinner.tsx
├── lib/
│   ├── api.ts          # API client functions
│   └── utils.ts        # Helper functions
├── hooks/
│   ├── useChat.ts      # Chat state management
│   └── useFileUpload.ts
└── types/
    └── index.ts        # TypeScript interfaces
```

## Common Patterns

### API Call Pattern
```typescript
const [loading, setLoading] = useState(false);
const [error, setError] = useState<string | null>(null);

const handleSend = async () => {
  setLoading(true);
  setError(null);
  try {
    const response = await sendMessage(message, conversationId);
    // handle response
  } catch (err) {
    setError("Не удалось отправить сообщение. Попробуйте ещё раз.");
  } finally {
    setLoading(false);
  }
};
```

### File Upload Pattern
```typescript
const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
  const file = e.target.files?.[0];
  if (!file) return;
  
  if (file.size > 10 * 1024 * 1024) {
    setError("Файл слишком большой. Максимум 10 МБ.");
    return;
  }
  
  setAttachedFile(file);
};
```

## Important Notes

1. **conversation_id**: Always save and pass back to maintain context
2. **Sources deduplication**: Same file may appear multiple times with different chunk_index - group by file_path for display
3. **Download URLs**: Already fully formed, just use as href
4. **Markdown in answers**: AI responses may include lists, bold, code blocks
5. **Long responses**: Auto-scroll to bottom as new content arrives
