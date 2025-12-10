# Lovable.dev Prompt for ALPACA Admin Dashboard

Create a lightweight, modern admin dashboard for monitoring and managing the ALPACA document processing system. This is a **development/testing tool** that should be clean, functional, and easily extensible.

## CRITICAL: Backend API is already running!

**The backend API is live and ready to use:**

- **API Base URL**: `https://api.alpaca-smart.com:8443/admin`
- **OpenAPI Spec**: `https://api.alpaca-smart.com:8443/admin/openapi.json`
- **Swagger UI**: `https://api.alpaca-smart.com:8443/admin/docs`
- **CORS**: Already configured, no issues expected

**DO NOT mock the API. Create real fetch calls to the endpoints specified.**

## Branding

### Logo & Identity
- **Name**: ALPACA (Alternative Language Processing And Content Analysis)
- **Logo**: Use 🦙 emoji as placeholder
- **Tagline**: "RAG Document Processing System"

### Color Palette
- **Primary**: Warm orange/amber (#F59E0B) - alpaca color theme
- **Secondary**: Soft teal (#14B8A6)
- **Background**: Light warm gray (#FAFAF9)
- **Cards**: White with subtle shadow
- **Text**: Dark gray (#1F2937)
- **Success**: Green (#10B981)
- **Warning**: Amber (#F59E0B)  
- **Error**: Red (#EF4444)

### Typography
- Font: Inter or system sans-serif
- Headers: Semi-bold
- Body: Regular weight
- Monospace for paths/hashes: JetBrains Mono or similar

## Design Principles

1. **Lightweight** - Fast loading, minimal dependencies
2. **Clean** - Generous whitespace, no clutter
3. **Functional** - Every element serves a purpose
4. **Extensible** - Easy to add new sections/features
5. **Developer-friendly** - Show technical details when needed

## ACTUAL API Response Structure

**IMPORTANT**: The API returns data in this exact structure. Use these exact property names!

```json
// GET /api/dashboard
{
  "files": {
    "total": 5877,
    "ok": 5872,
    "error": 5,
    "added": 0,
    "updated": 0,
    "processed": 0,
    "deleted": 0
  },
  "chunks": {
    "total_chunks": 153084,
    "unique_files": 5875,
    "avg_chunks_per_file": 26.06
  },
  "queue": {
    "added": [],
    "updated": [],
    "deleted": []
  },
  "errors": [
    {
      "file_path": "path/to/file.docx",
      "file_hash": "abc123...",
      "file_size": 12079,
      "last_checked": "2025-12-05T05:43:15.942878"
    }
  ],
  "health": {
    "status": "healthy",
    "connected": true,
    "pgvector_version": "0.8.0",
    "table_sizes": {
      "files": "61 MB",
      "chunks": "1952 MB"
    }
  },
  "ollama": {
    "status": "healthy",
    "url": "http://172.17.0.1:11434",
    "loaded_models": [
      {
        "name": "qwen2.5:32b",
        "size_vram_mb": 22019,
        "parameter_size": "32.8B",
        "quantization": "Q4_K_M",
        "family": "qwen2"
      },
      {
        "name": "bge-m3:latest",
        "size_vram_mb": 1635,
        "parameter_size": "566.70M",
        "quantization": "F16",
        "family": "bert"
      }
    ],
    "total_vram_mb": 23654
  }
}
```

## Layout Structure

```
┌─────────────────────────────────────────────────────────────┐
│  🦙 ALPACA Admin                           [Refresh] [⚙️]   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐       │
│  │ 📁 5,877 │ │ ⏳ 0     │ │ ✅ 5,872 │ │ ❌ 5     │       │
│  │  Total   │ │  Queue   │ │ Indexed  │ │  Errors  │       │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘       │
│                                                             │
│  ┌─────────────────────┐  ┌─────────────────────────────┐  │
│  │ Vector Database     │  │ 🤖 Ollama Status            │  │
│  │ ─────────────────── │  │ ─────────────────────────── │  │
│  │ Chunks: 153,084     │  │ ● Healthy | 23.6 GB VRAM    │  │
│  │ Documents: 5,875    │  │ qwen2.5:32b (22 GB)         │  │
│  │ Avg: 26 chunks/doc  │  │ bge-m3 (1.6 GB)             │  │
│  │ Storage: 1.9 GB     │  │ [Run Speed Test]            │  │
│  └─────────────────────┘  └─────────────────────────────┘  │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Recent Errors (5)                                   │   │
│  │ ─────────────────────────────────────────────────── │   │
│  │ ❌ Прошито и пронумеровано.docx                     │   │
│  │    4 days ago │ Корпоративные документы/...         │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Core Features

### 1. Stats Cards (Top Row)

Four key metrics from `data.files`:
- **Total Files** - `data?.files?.total ?? 0`
- **Queue** - `(data?.files?.added ?? 0) + (data?.files?.updated ?? 0) + (data?.files?.deleted ?? 0)`
- **Indexed** - `data?.files?.ok ?? 0`
- **Errors** - `data?.files?.error ?? 0`

### 2. Vector Database Stats

From `data.chunks`:
- Total chunks: `data?.chunks?.total_chunks`
- Unique documents: `data?.chunks?.unique_files`
- Average: `data?.chunks?.avg_chunks_per_file`

From `data.health.table_sizes`:
- Storage: `data?.health?.table_sizes?.chunks`

### 3. Ollama Status

From `data.ollama`:
- Status indicator: green if `data?.ollama?.status === "healthy"`
- VRAM: `(data?.ollama?.total_vram_mb / 1024).toFixed(1) + " GB"`
- Models list: `data?.ollama?.loaded_models ?? []`

**Speed Test Button**: Calls `GET /api/ollama/speed-test` and shows `tokens_per_second`.
Normal speed for RTX 3090: 30-40 tok/s. If < 5 tok/s, model runs on CPU!

### 4. Processing Queue

Queue is an OBJECT with arrays, not a single array!
```typescript
const queueItems = [
  ...(data?.queue?.added ?? []).map(item => ({...item, status: 'added'})),
  ...(data?.queue?.updated ?? []).map(item => ({...item, status: 'updated'})),
  ...(data?.queue?.deleted ?? []).map(item => ({...item, status: 'deleted'}))
];
```

### 5. Recent Errors

From `data.errors` (array):
```typescript
const errors = data?.errors ?? [];
// Each error has: file_path, file_hash, file_size, last_checked
```

## API Endpoints Reference

### Main Dashboard
```
GET /api/dashboard - all data in one request (use this!)
```

### Individual Endpoints (if needed)
```
GET /api/files/stats - file statistics
GET /api/files/list?status=added&limit=20 - file list with filters
GET /api/files/queue - processing queue
GET /api/files/errors - error files
GET /api/chunks/stats - vector database stats
GET /api/ollama/status - detailed Ollama status
GET /api/ollama/speed-test?model=qwen2.5:32b&num_predict=50 - speed test
GET /health - system health
```

## Critical: Data Handling

**ALWAYS use optional chaining and defaults to prevent runtime errors!**

```typescript
// ✅ CORRECT - safe access with defaults
const total = data?.files?.total ?? 0;
const indexed = data?.files?.ok ?? 0;
const errors = data?.files?.error ?? 0;
const chunks = data?.chunks?.total_chunks ?? 0;
const models = data?.ollama?.loaded_models ?? [];
const errorList = data?.errors ?? [];

// Queue is an object with arrays
const queueCount = 
  (data?.queue?.added?.length ?? 0) + 
  (data?.queue?.updated?.length ?? 0) + 
  (data?.queue?.deleted?.length ?? 0);

// ❌ WRONG - will crash if data is undefined
const total = data.files.total;  // TypeError!
```

**Loading State**:
```typescript
if (isLoading || !data) {
  return (
    <div className="flex items-center justify-center h-screen">
      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-amber-500"></div>
    </div>
  );
}
```

## Interactive Features

### Auto-Refresh
- Toggle for auto-refresh (every 10/30/60 seconds)
- Manual refresh button
- Show "Last updated: X seconds ago"

### Settings Panel (⚙️)
- API URL configuration (stored in localStorage)
- Refresh interval selector
- Show/hide sections

## Responsive Design

- Mobile-friendly (stack cards vertically on small screens)
- Collapsible sections on mobile
- Touch-friendly buttons

## Code Organization

```
src/
├── components/
│   ├── StatsCard.tsx
│   ├── VectorDBCard.tsx
│   ├── OllamaCard.tsx
│   ├── ErrorList.tsx
│   └── QueueList.tsx
├── hooks/
│   ├── useDashboard.ts    # fetches /api/dashboard
│   └── useAutoRefresh.ts
├── services/
│   └── api.ts             # API base URL, fetch wrapper
├── types/
│   └── dashboard.ts       # TypeScript interfaces
└── pages/
    └── Dashboard.tsx
```

## First Prompt to Lovable

Copy this to start:

---

Create an admin dashboard for ALPACA document processing system.

API: https://api.alpaca-smart.com:8443/admin

Use GET /api/dashboard which returns all data in one request.

CRITICAL - API response structure (use exact property names):
- files: { total, ok, error, added, updated, processed, deleted }
- chunks: { total_chunks, unique_files, avg_chunks_per_file }
- queue: { added: [], updated: [], deleted: [] } - object with arrays!
- errors: [] - array of error files
- ollama: { status, total_vram_mb, loaded_models: [] }
- health: { status, table_sizes: { files, chunks } }

Features:
1. Stats cards: Total (files.total), Queue (added+updated+deleted count), Indexed (files.ok), Errors (files.error)
2. Vector database card: chunks count, unique files, storage size
3. Ollama status card: health indicator, VRAM usage, loaded models list, speed test button
4. Recent errors list
5. Auto-refresh toggle
6. Loading spinner

IMPORTANT - prevent runtime errors:
- Always use optional chaining: data?.files?.total ?? 0
- Queue is object with arrays: data?.queue?.added ?? []
- Show loading spinner while data is undefined

Style:
- Warm orange/amber accent (#F59E0B)
- Light background (#FAFAF9)
- Clean, minimal
- Use 🦙 emoji in header

Start with fetching /api/dashboard and displaying stats cards.

---
