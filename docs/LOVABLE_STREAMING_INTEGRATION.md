# Streaming Chat Integration Guide for Lovable.dev

This guide explains how to integrate the ALPACA Chat API streaming endpoint into your Lovable.dev frontend application.

## API Endpoint

**URL:** `https://api.alpaca-smart.com:8443/chat/api/chat/stream`  
**Method:** `POST`  
**Content-Type:** `application/json`

### Request Body

```json
{
  "message": "Your question here",
  "conversation_id": "optional-uuid-for-conversation-tracking"
}
```

### Response Format (Server-Sent Events)

The endpoint returns a stream of SSE events:

| Event | Description | Data Format |
|-------|-------------|-------------|
| `metadata` | First event with sources and conversation ID | `{"conversation_id": "uuid", "sources": [...]}` |
| `chunk` | LLM response fragment | `{"content": "text"}` |
| `done` | Generation complete | `{}` |
| `error` | Error occurred | `{"error": "message"}` |

## Implementation

### 1. Create a Custom Hook for Streaming Chat

Create a new file `src/hooks/useStreamingChat.ts`:

```typescript
import { useState, useCallback, useRef } from 'react';

interface Source {
  file_path: string;
  file_name: string;
  chunk_index: number;
  similarity: number;
  download_url: string;
  title: string | null;
  summary: string | null;
  category: string | null;
  modified_at: string | null;
}

interface StreamingChatState {
  answer: string;
  sources: Source[];
  conversationId: string | null;
  isLoading: boolean;
  error: string | null;
}

const API_URL = 'https://api.alpaca-smart.com:8443/chat/api/chat/stream';

export function useStreamingChat() {
  const [state, setState] = useState<StreamingChatState>({
    answer: '',
    sources: [],
    conversationId: null,
    isLoading: false,
    error: null,
  });
  
  // Use ref to accumulate answer for immediate updates
  const answerRef = useRef('');

  const sendMessage = useCallback(async (
    message: string,
    conversationId?: string
  ) => {
    // Reset state for new message
    answerRef.current = '';
    setState(prev => ({
      ...prev,
      answer: '',
      sources: [],
      isLoading: true,
      error: null,
    }));

    try {
      const response = await fetch(API_URL, {
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
        throw new Error(`HTTP error: ${response.status}`);
      }

      const reader = response.body?.getReader();
      if (!reader) {
        throw new Error('No response body');
      }

      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        
        // SSE format: "event: type\ndata: json\n\n"
        // Process complete events (ending with double newline)
        const events = buffer.split('\n\n');
        buffer = events.pop() || ''; // Keep incomplete event in buffer

        for (const eventBlock of events) {
          if (!eventBlock.trim()) continue;
          
          const lines = eventBlock.split('\n');
          let eventType = '';
          let eventData = '';

          for (const line of lines) {
            if (line.startsWith('event: ')) {
              eventType = line.slice(7).trim();
            } else if (line.startsWith('data: ')) {
              eventData = line.slice(6);
            }
          }

          if (!eventType || !eventData) continue;

          try {
            const data = JSON.parse(eventData);
            
            switch (eventType) {
              case 'metadata':
                setState(prev => ({
                  ...prev,
                  sources: data.sources,
                  conversationId: data.conversation_id,
                }));
                break;
              
              case 'chunk':
                // Accumulate in ref and update state
                answerRef.current += data.content;
                setState(prev => ({
                  ...prev,
                  answer: answerRef.current,
                }));
                break;
              
              case 'done':
                setState(prev => ({ ...prev, isLoading: false }));
                break;
              
              case 'error':
                setState(prev => ({
                  ...prev,
                  error: data.error,
                  isLoading: false,
                }));
                break;
            }
          } catch (parseError) {
            console.warn('Failed to parse SSE data:', eventData);
          }
        }
      }
      
      // Ensure loading is false when stream ends
      setState(prev => ({ ...prev, isLoading: false }));
      
    } catch (err) {
      setState(prev => ({
        ...prev,
        error: err instanceof Error ? err.message : 'Unknown error',
        isLoading: false,
      }));
    }
  }, []);

  const reset = useCallback(() => {
    answerRef.current = '';
    setState({
      answer: '',
      sources: [],
      conversationId: null,
      isLoading: false,
      error: null,
    });
  }, []);

  return {
    ...state,
    sendMessage,
    reset,
  };
}
```

### 2. Create a Chat Component

Create `src/components/Chat.tsx`:

```tsx
import React, { useState } from 'react';
import { useStreamingChat } from '@/hooks/useStreamingChat';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Loader2, FileText, Download } from 'lucide-react';

export function Chat() {
  const [input, setInput] = useState('');
  const { 
    answer, 
    sources, 
    conversationId,
    isLoading, 
    error, 
    sendMessage 
  } = useStreamingChat();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (input.trim() && !isLoading) {
      sendMessage(input, conversationId || undefined);
      setInput('');
    }
  };

  return (
    <div className="flex flex-col h-full max-w-4xl mx-auto p-4 gap-4">
      {/* Answer Section */}
      <Card className="flex-1 overflow-auto">
        <CardHeader>
          <CardTitle>Answer</CardTitle>
        </CardHeader>
        <CardContent>
          {error ? (
            <p className="text-red-500">Error: {error}</p>
          ) : answer ? (
            <div className="prose prose-sm max-w-none whitespace-pre-wrap">
              {answer}
              {isLoading && <span className="animate-pulse">▊</span>}
            </div>
          ) : (
            <p className="text-muted-foreground">
              Ask a question to get started...
            </p>
          )}
        </CardContent>
      </Card>

      {/* Sources Section */}
      {sources.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Sources ({sources.length})</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid gap-2">
              {sources.map((source, idx) => (
                <div 
                  key={idx}
                  className="flex items-center justify-between p-2 rounded-lg bg-muted/50"
                >
                  <div className="flex items-center gap-2 min-w-0">
                    <FileText className="h-4 w-4 shrink-0 text-muted-foreground" />
                    <div className="min-w-0">
                      <p className="text-sm font-medium truncate">
                        {source.title || source.file_name}
                      </p>
                      {source.category && (
                        <p className="text-xs text-muted-foreground">
                          {source.category}
                        </p>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <span className="text-xs text-muted-foreground">
                      {(source.similarity * 100).toFixed(0)}%
                    </span>
                    <a 
                      href={source.download_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-primary hover:text-primary/80"
                    >
                      <Download className="h-4 w-4" />
                    </a>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Input Section */}
      <form onSubmit={handleSubmit} className="flex gap-2">
        <Input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask a question..."
          disabled={isLoading}
          className="flex-1"
        />
        <Button type="submit" disabled={isLoading || !input.trim()}>
          {isLoading ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            'Send'
          )}
        </Button>
      </form>
    </div>
  );
}
```

### 3. Alternative: Using EventSource API

If you prefer the native EventSource API (simpler but less control):

```typescript
// Note: EventSource only supports GET, so we need a workaround
// Using fetch with ReadableStream is recommended (shown above)

// However, for POST requests, you can use a library like @microsoft/fetch-event-source:
import { fetchEventSource } from '@microsoft/fetch-event-source';

async function streamChat(message: string, onChunk: (text: string) => void) {
  await fetchEventSource('https://api.alpaca-smart.com:8443/chat/api/chat/stream', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ message }),
    onmessage(ev) {
      if (ev.event === 'chunk') {
        const data = JSON.parse(ev.data);
        onChunk(data.content);
      }
    },
  });
}
```

To use this approach, install the package:
```bash
npm install @microsoft/fetch-event-source
```

### 4. RECOMMENDED: Using @microsoft/fetch-event-source (Most Reliable)

**This is the most reliable approach for SSE streaming in React.**  
The native fetch API can have issues with buffering in some browsers.

```bash
npm install @microsoft/fetch-event-source
```

Create `src/hooks/useStreamingChat.ts`:

```typescript
import { useState, useCallback, useRef } from 'react';
import { fetchEventSource } from '@microsoft/fetch-event-source';

interface Source {
  file_path: string;
  file_name: string;
  chunk_index: number;
  similarity: number;
  download_url: string;
  title: string | null;
  summary: string | null;
  category: string | null;
  modified_at: string | null;
}

interface StreamingChatState {
  answer: string;
  sources: Source[];
  conversationId: string | null;
  isLoading: boolean;
  error: string | null;
}

const API_URL = 'https://api.alpaca-smart.com:8443/chat/api/chat/stream';

export function useStreamingChat() {
  const [state, setState] = useState<StreamingChatState>({
    answer: '',
    sources: [],
    conversationId: null,
    isLoading: false,
    error: null,
  });
  
  const answerRef = useRef('');
  const abortControllerRef = useRef<AbortController | null>(null);

  const sendMessage = useCallback(async (
    message: string,
    conversationId?: string
  ) => {
    // Abort previous request if any
    abortControllerRef.current?.abort();
    abortControllerRef.current = new AbortController();
    
    // Reset state
    answerRef.current = '';
    setState({
      answer: '',
      sources: [],
      conversationId: conversationId || null,
      isLoading: true,
      error: null,
    });

    try {
      await fetchEventSource(API_URL, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message,
          conversation_id: conversationId,
        }),
        signal: abortControllerRef.current.signal,
        
        onopen: async (response) => {
          if (!response.ok) {
            throw new Error(`HTTP error: ${response.status}`);
          }
        },
        
        onmessage: (ev) => {
          if (!ev.data) return;
          
          try {
            const data = JSON.parse(ev.data);
            
            switch (ev.event) {
              case 'metadata':
                setState(prev => ({
                  ...prev,
                  sources: data.sources || [],
                  conversationId: data.conversation_id,
                }));
                break;
              
              case 'chunk':
                answerRef.current += data.content || '';
                setState(prev => ({
                  ...prev,
                  answer: answerRef.current,
                }));
                break;
              
              case 'done':
                setState(prev => ({ ...prev, isLoading: false }));
                break;
              
              case 'error':
                setState(prev => ({
                  ...prev,
                  error: data.error || 'Unknown error',
                  isLoading: false,
                }));
                break;
            }
          } catch (e) {
            console.warn('Failed to parse event data:', ev.data);
          }
        },
        
        onclose: () => {
          setState(prev => ({ ...prev, isLoading: false }));
        },
        
        onerror: (err) => {
          console.error('SSE error:', err);
          setState(prev => ({
            ...prev,
            error: err instanceof Error ? err.message : 'Connection error',
            isLoading: false,
          }));
          // Don't retry on error
          throw err;
        },
      });
    } catch (err) {
      if (err instanceof Error && err.name === 'AbortError') {
        // Request was aborted, ignore
        return;
      }
      setState(prev => ({
        ...prev,
        error: err instanceof Error ? err.message : 'Unknown error',
        isLoading: false,
      }));
    }
  }, []);

  const stop = useCallback(() => {
    abortControllerRef.current?.abort();
    setState(prev => ({ ...prev, isLoading: false }));
  }, []);

  const reset = useCallback(() => {
    abortControllerRef.current?.abort();
    answerRef.current = '';
    setState({
      answer: '',
      sources: [],
      conversationId: null,
      isLoading: false,
      error: null,
    });
  }, []);

  return {
    ...state,
    sendMessage,
    stop,
    reset,
  };
}
```

**Why this approach is better:**
- ✅ Properly handles SSE protocol
- ✅ No buffering issues
- ✅ Built-in reconnection logic (disabled in our case)
- ✅ Proper error handling
- ✅ AbortController support for cancellation

## Source Metadata Fields

Each source in the `metadata` event contains:

| Field | Type | Description |
|-------|------|-------------|
| `file_path` | string | Relative path to the document |
| `file_name` | string | Document filename |
| `chunk_index` | number | Index of the relevant chunk |
| `similarity` | number | Relevance score (0.0 - 1.0) |
| `download_url` | string | Direct download link |
| `title` | string \| null | Document title (if extracted) |
| `summary` | string \| null | Brief document summary |
| `category` | string \| null | Document category (see list below) |
| `modified_at` | string \| null | Last modification date (ISO format) |

### Document Categories

Possible values for the `category` field:
- Договор подряда (Contract work)
- Договор купли-продажи (Sales contract)
- Трудовой договор (Employment contract)
- Протокол, меморандум (Protocol, memorandum)
- Доверенность (Power of attorney)
- Акт выполненных работ (Work completion act)
- Счет-фактура, счет (Invoice)
- Техническая документация (Technical documentation)
- Презентация (Presentation)
- Письмо (Letter)
- Бухгалтерская документация (Accounting documentation)
- Инструкция, регламент (Instruction, regulation)
- Статья, публикация, книга (Article, publication, book)
- Прочее (Other)

## Error Handling

Always handle potential errors:

```typescript
// Connection errors
if (!response.ok) {
  // Server returned an error status
  throw new Error(`Server error: ${response.status}`);
}

// Stream errors (sent via SSE)
case 'error':
  // Handle error from the stream
  console.error('Stream error:', data.error);
  break;

// Network errors
catch (err) {
  // Handle network/parsing errors
  console.error('Request failed:', err);
}
```

## CORS Configuration

The API is configured to accept requests from any origin. If you encounter CORS issues, ensure you're:
1. Using HTTPS
2. Not sending custom headers that require preflight

## Troubleshooting

### Stream appears all at once instead of progressively

**Cause:** Browser or proxy buffering SSE responses.

**Solutions:**

1. **Use `@microsoft/fetch-event-source`** (Recommended)
   - Install: `npm install @microsoft/fetch-event-source`
   - See Section 4 above for implementation
   - This library properly handles SSE streaming

2. **Check for proxy buffering**
   - If using a reverse proxy (nginx, Cloudflare), disable buffering:
   ```nginx
   proxy_buffering off;
   X-Accel-Buffering: no;
   ```

3. **Verify the API response headers**
   The API sends these headers to prevent buffering:
   ```
   Cache-Control: no-cache
   Connection: keep-alive
   X-Accel-Buffering: no
   ```

### "Failed to fetch" or CORS errors

1. Ensure you're using HTTPS URL
2. Check that the API is accessible: test with curl first
3. Verify no browser extensions are blocking requests

### Stream stops unexpectedly

1. Check browser console for errors
2. The default timeout is 300 seconds (5 minutes)
3. Use the `stop()` function to cleanly abort if needed

### Large metadata event causes parsing issues

The first `metadata` event can be large (contains all sources). Ensure your JSON parser can handle it. The recommended `@microsoft/fetch-event-source` handles this correctly.

## Testing

Test the endpoint using curl:

```bash
curl -N -X POST https://api.alpaca-smart.com:8443/chat/api/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"message": "What is a contract?"}'
```

## Non-Streaming Alternative

If you prefer a simpler JSON response without streaming:

**URL:** `https://api.alpaca-smart.com:8443/chat/api/chat`  
**Method:** `POST`

```typescript
const response = await fetch('https://api.alpaca-smart.com:8443/chat/api/chat', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ message: 'Your question' }),
});

const data = await response.json();
// data = { answer: "...", conversation_id: "...", sources: [...] }
```
