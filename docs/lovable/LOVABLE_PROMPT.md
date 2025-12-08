# Lovable.dev Prompt for ALPACA Chat Interface

Create a modern, lightweight chat interface for an enterprise RAG (Retrieval Augmented Generation) system called ALPACA. 

## CRITICAL: Backend API is already running!

**The backend API is live and ready to use. You MUST connect to it:**

- **API Base URL**: `https://api.alpaca-smart.com:8443/chat`
- **CORS**: Already configured, no issues expected
- **Endpoints**: See API Integration section below

**DO NOT mock the API. Create real fetch calls to the endpoints specified.**

## Design Requirements

### Visual Style
- **Clean, light, minimalist design** - avoid visual clutter
- White/light gray background with subtle shadows
- Modern sans-serif font (Inter or similar)
- Accent color: soft blue (#3B82F6) for interactive elements
- Rounded corners on all elements (8-12px radius)
- Generous whitespace and padding

### Layout
- Full-height chat interface (like ChatGPT or Claude)
- Messages area takes most of the screen with auto-scroll
- Fixed input area at the bottom
- Optional: collapsible sidebar for conversation history (future feature)

## Core Features

### 1. Chat Messages

**User messages:**
- Right-aligned, blue background
- Show timestamp on hover

**AI responses:**
- Left-aligned, light gray background
- Support Markdown rendering (bold, lists, code blocks, etc.)
- **Loading state**: Show animated spinner/dots while waiting for response
- Smooth fade-in animation when response arrives

### 2. Source Documents (Citations)

After each AI response, display source documents as **subtle, non-intrusive chips/tags**:

```
┌─────────────────────────────────────────┐
│ AI Response text here...                │
│                                         │
│ 📎 Sources:                             │
│ [📄 Устав.docx] [📄 Договор.pdf] [+2]   │
└─────────────────────────────────────────┘
```

- Small, pill-shaped badges (not cards)
- Show file icon + shortened filename (max 15-20 chars with ellipsis)
- Click to download the file
- If more than 3 sources, show "+N more" expandable
- Tooltip on hover showing full path and similarity score

### 3. Message Input

- Text input field with placeholder: "Задайте вопрос по документам..."
- **Paperclip icon (📎)** on the left for file attachment
- Send button on the right (arrow icon)
- Support Enter to send, Shift+Enter for new line
- Disable send while waiting for response

### 4. File Attachment

When user clicks paperclip:
- Open file picker (accept: .docx, .pdf, .txt, .xlsx, .pptx)
- Show attached file as a small chip above the input:
  ```
  ┌──────────────────────────────────────┐
  │ [📄 report.docx ✕]                   │
  ├──────────────────────────────────────┤
  │ [📎] Type your message...    [Send]  │
  └──────────────────────────────────────┘
  ```
- Allow removing attachment before sending
- Max file size: 10 MB (show error if exceeded)

### 5. Error Handling

- Show toast notifications for errors
- Retry button if request fails
- Graceful handling of network issues

## API Integration

**IMPORTANT: Create a working API integration with this exact configuration:**

### API Configuration

Create file `src/lib/api.ts`:

```typescript
const API_BASE_URL = "https://api.alpaca-smart.com:8443/chat";

export interface Source {
  file_path: string;
  file_name: string;
  chunk_index: number;
  similarity: number;
  download_url: string;
}

export interface ChatResponse {
  answer: string;
  conversation_id: string;
  sources: Source[];
  attachment?: {
    filename: string;
    size: number;
    content_type: string;
  };
}

export async function sendMessage(
  message: string,
  conversationId?: string
): Promise<ChatResponse> {
  const response = await fetch(`${API_BASE_URL}/api/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      message,
      conversation_id: conversationId,
    }),
  });

  if (!response.ok) {
    throw new Error(`API error: ${response.status}`);
  }

  return response.json();
}

export async function sendMessageWithFile(
  message: string,
  file?: File,
  conversationId?: string
): Promise<ChatResponse> {
  const formData = new FormData();
  formData.append("message", message);

  if (conversationId) {
    formData.append("conversation_id", conversationId);
  }

  if (file) {
    formData.append("file", file);
  }

  const response = await fetch(`${API_BASE_URL}/api/chat/with-file`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    throw new Error(`API error: ${response.status}`);
  }

  return response.json();
}

export async function getStats(): Promise<{ total_chunks: number; unique_files: number }> {
  const response = await fetch(`${API_BASE_URL}/api/chat/stats`);
  return response.json();
}
```

### API Endpoints Summary

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/chat` | POST | Send message (JSON) |
| `/api/chat/with-file` | POST | Send message with file (multipart/form-data) |
| `/api/chat/stats` | GET | Get knowledge base stats |

### Response Structure

```typescript
// Response from /api/chat
{
  "answer": "AI response with markdown support",
  "conversation_id": "uuid-to-save-and-reuse",
  "sources": [
    {
      "file_path": "Folder/Document.docx",
      "file_name": "Document.docx", 
      "chunk_index": 15,
      "similarity": 0.66,
      "download_url": "https://api.alpaca-smart.com:8443/chat/api/files/download?path=..."
    }
  ]
}
```

### Get Stats (optional, for header/footer)
```typescript
GET /api/chat/stats

Response:
{
  "total_chunks": 1234,
  "unique_files": 56
}
```

## Technical Requirements

1. **React** with TypeScript
2. **Tailwind CSS** for styling
3. Use **react-markdown** for rendering AI responses
4. Store conversation_id in state to maintain context
5. Set request timeout to 120 seconds (LLM can be slow)
6. Implement proper loading states
7. Auto-scroll to bottom on new messages
8. Mobile-responsive design
9. **Use the exact API code from `src/lib/api.ts` shown above** - do not mock or simulate

## Component Structure

```
App
├── Header (logo, optional stats badge)
├── ChatContainer
│   ├── MessageList
│   │   ├── UserMessage
│   │   └── AIMessage
│   │       ├── MarkdownContent
│   │       └── SourceChips
│   └── LoadingIndicator (spinner)
├── InputArea
│   ├── AttachmentPreview
│   ├── FileUploadButton (paperclip)
│   ├── TextInput
│   └── SendButton
└── ToastNotifications
```

## Sample UI States

### Empty State
```
┌─────────────────────────────────────────┐
│            🦙 ALPACA                    │
│                                         │
│     Задайте вопрос по документам        │
│     компании, и я найду ответ           │
│                                         │
│  [📎] Введите ваш вопрос...     [➤]    │
└─────────────────────────────────────────┘
```

### Loading State  
```
│ User: Какие обязанности у директора?    │
│                                         │
│ 🦙 ●●● (typing indicator)               │
```

### Response with Sources
```
│ User: Какие обязанности у директора?    │
│                                         │
│ 🦙 Согласно уставу компании,            │
│    директор отвечает за:                │
│    • Текущее управление                 │
│    • Выполнение решений совета          │
│    • Кадровую политику                  │
│                                         │
│    📎 [Устав.docx] [Положение.pdf]      │
└─────────────────────────────────────────┘
```

## Additional Notes

- The system is for a Russian-speaking enterprise, so UI text should be in Russian
- File names in sources are often in Russian (Cyrillic)
- The llama emoji (🦙) or alpaca image can be used as the AI avatar
- Keep the interface professional but friendly
