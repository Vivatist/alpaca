# 🔄 TXT Parser - Process Flow

## 📊 3-Stage Pipeline

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          TXT PARSER WORKFLOW                                │
└─────────────────────────────────────────────────────────────────────────────┘

INPUT: Plain text file (.txt)
    │
    ├─ contract.txt (Windows-1251)
    ├─ notes.txt (UTF-8)
    └─ legacy_doc.txt (CP866)

    ↓

╔═════════════════════════════════════════════════════════════════════════════╗
║ STAGE 1: DETECT ENCODING                                                   ║
╠═════════════════════════════════════════════════════════════════════════════╣
║                                                                             ║
║  1. Read first 10KB of file                                                ║
║     └─ Enough for accurate detection                                       ║
║                                                                             ║
║  2. Use chardet library                                                    ║
║     └─ detected = chardet.detect(raw_data)                                 ║
║                                                                             ║
║  3. Check confidence                                                       ║
║     ├─ confidence >= 0.7 → Use detected encoding                           ║
║     └─ confidence < 0.7  → Fallback to UTF-8                               ║
║                                                                             ║
║  Output: encoding string (utf-8, windows-1251, cp866, etc.)                ║
║                                                                             ║
╚═════════════════════════════════════════════════════════════════════════════╝

    ↓

╔═════════════════════════════════════════════════════════════════════════════╗
║ STAGE 2: READ & EXTRACT METADATA                                           ║
╠═════════════════════════════════════════════════════════════════════════════╣
║                                                                             ║
║  1. Open file with detected encoding                                       ║
║     └─ with open(file_path, 'r', encoding=detected_encoding)               ║
║                                                                             ║
║  2. Read all content                                                       ║
║     └─ content = f.read()                                                  ║
║                                                                             ║
║  3. Extract metrics                                                        ║
║     ├─ lines = content.count('\n') + 1                                     ║
║     ├─ words = len(content.split())                                        ║
║     └─ characters = len(content)                                           ║
║                                                                             ║
║  4. Get file stats                                                         ║
║     ├─ size_bytes = stat.st_size                                           ║
║     ├─ created = stat.st_ctime                                             ║
║     └─ modified = stat.st_mtime                                            ║
║                                                                             ║
║  Output: {content: str, metadata: dict}                                    ║
║                                                                             ║
╚═════════════════════════════════════════════════════════════════════════════╝

    ↓

╔═════════════════════════════════════════════════════════════════════════════╗
║ STAGE 3: FORMAT AS MARKDOWN                                                ║
╠═════════════════════════════════════════════════════════════════════════════╣
║                                                                             ║
║  1. Generate title from filename                                           ║
║     └─ title = Path(file_path).stem                                        ║
║                                                                             ║
║  2. Preserve text structure                                                ║
║     ├─ Keep paragraph breaks (empty lines)                                 ║
║     ├─ Keep indentation (spaces/tabs)                                      ║
║     └─ Keep line breaks                                                    ║
║                                                                             ║
║  3. Add Markdown heading                                                   ║
║     └─ markdown = f"# {title}\n\n{content}"                                ║
║                                                                             ║
║  4. Generate YAML frontmatter                                              ║
║     ├─ document_type: txt                                                  ║
║     ├─ file_name, file_path, parsed_date                                   ║
║     ├─ encoding (КРИТИЧНО!)                                                ║
║     └─ lines, words, characters, size_bytes, dates                         ║
║                                                                             ║
║  Output: Complete Markdown document with YAML header                       ║
║                                                                             ║
╚═════════════════════════════════════════════════════════════════════════════╝

    ↓

╔═════════════════════════════════════════════════════════════════════════════╗
║ MARKDOWN WRITER (Centralized Module)                                       ║
╠═════════════════════════════════════════════════════════════════════════════╣
║                                                                             ║
║  1. Transliterate filename                                                 ║
║     └─ contract_договор → contract_dogovor                                 ║
║                                                                             ║
║  2. Generate timestamp                                                     ║
║     └─ 20251028_103045_123                                                 ║
║                                                                             ║
║  3. Construct safe filename                                                ║
║     └─ 20251028_103045_123_contract_dogovor.md                             ║
║                                                                             ║
║  4. Write to /volume_md                                                    ║
║     └─ Atomic write + fsync for durability                                 ║
║                                                                             ║
║  Output: {file_name, file_path, size}                                      ║
║                                                                             ║
╚═════════════════════════════════════════════════════════════════════════════╝

    ↓

OUTPUT: Markdown file in /volume_md
    │
    └─ 20251028_103045_123_contract.md
       ├─ YAML frontmatter with encoding metadata
       └─ Formatted Markdown content

```

---

## ⚡ Performance Characteristics

```
┌─────────────────────────────────────────────────────────────┐
│                    TIMING BREAKDOWN                         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Stage 1: Detect Encoding           2-3ms   ████░░░░░░     │
│  Stage 2: Read & Extract            5-7ms   █████████░     │
│  Stage 3: Format Markdown           1-2ms   ██░░░░░░░░     │
│  MarkdownWriter.save()              1-2ms   ██░░░░░░░░     │
│                                                             │
│  ─────────────────────────────────────────────────────     │
│  TOTAL:                            10-15ms  ████████████   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**Сравнение:**
- TXT: **15ms** ⚡ (baseline - fastest)
- Word: **500ms** 🐌 (33x slower - markitdown conversion)
- PDF: **1500ms** 🐢 (100x slower - pypdf parsing)
- PDF+OCR: **155000ms** 🦥 (10000x slower - Tesseract)

---

## 🔄 Data Flow Example

### Input File: `contract.txt` (Windows-1251)

```
Договор поставки №123

Настоящий договор заключён между:
- ООО "Компания А"
- ООО "Компания Б"

Предмет договора:
Поставка оборудования согласно спецификации.
```

### Stage 1 Output: Detected Encoding

```python
{
    'encoding': 'windows-1251',
    'confidence': 0.95,
    'language': 'Russian'
}
```

### Stage 2 Output: Content + Metadata

```python
{
    'content': 'Договор поставки №123\n\nНастоящий договор...',
    'metadata': {
        'title': 'contract',
        'encoding': 'windows-1251',
        'lines': 8,
        'words': 25,
        'characters': 180,
        'size_bytes': 256,
        'created': '2024-01-15T09:30:00',
        'modified': '2024-02-20T14:45:00'
    }
}
```

### Stage 3 Output: Formatted Markdown

```markdown
---
document_type: txt
file_name: contract.txt
file_path: /app/data/volume_documents/contract.txt
parsed_date: 2025-10-28T10:30:45.123456Z
parser: alpaca-txt-parser
title: contract
encoding: windows-1251
lines: 8
characters: 180
words: 25
size_bytes: 256
created: '2024-01-15T09:30:00'
modified: '2024-02-20T14:45:00'
---

# contract

Договор поставки №123

Настоящий договор заключён между:
- ООО "Компания А"
- ООО "Компания Б"

Предмет договора:
Поставка оборудования согласно спецификации.
```

### Final Output: Saved File

```
/volume_md/20251028_103045_123_contract.md
Size: 533 bytes
Permissions: rw-r--r--
```

---

## 🧪 Test Scenarios

### Scenario 1: UTF-8 Modern Document

```
INPUT: notes_2024.txt (UTF-8)
    ↓
Stage 1: encoding=utf-8, confidence=0.99
    ↓
Stage 2: lines=50, words=500, chars=3000
    ↓
Stage 3: Markdown with UTF-8 metadata
    ↓
OUTPUT: 20251028_103045_123_notes_2024.md
```

**Processing time:** 10ms

---

### Scenario 2: Legacy Windows-1251 Document

```
INPUT: legacy_contract.txt (Windows-1251)
    ↓
Stage 1: encoding=windows-1251, confidence=0.95
    ↓
Stage 2: lines=200, words=2000, chars=12000
    ↓
Stage 3: Markdown with Windows-1251 metadata
    ↓
OUTPUT: 20251028_103045_456_legacy_contract.md
```

**Processing time:** 15ms

---

### Scenario 3: Low Confidence Fallback

```
INPUT: mixed_encoding.txt (Unknown)
    ↓
Stage 1: encoding=iso-8859-1, confidence=0.45 → FALLBACK to utf-8
    ↓
Stage 2: Read with UTF-8 → Success
    ↓
Stage 3: Markdown with utf-8 metadata + WARNING logged
    ↓
OUTPUT: 20251028_103045_789_mixed_encoding.md
```

**Processing time:** 12ms
**Log:** `[WARNING] Low encoding confidence | detected=iso-8859-1 confidence=0.45`

---

### Scenario 4: Empty File

```
INPUT: empty.txt (0 bytes)
    ↓
Stage 1: encoding=utf-8 (default)
    ↓
Stage 2: lines=1, words=0, chars=0
    ↓
Stage 3: Markdown with title only
    ↓
OUTPUT: 20251028_103045_000_empty.md
```

**Processing time:** 8ms
**Log:** `[WARNING] Empty file | file=empty.txt`

---

## 🔗 Integration Points

### Celery Task Wrapper

```python
# tasks/txt_tasks.py
@app.task(name='tasks.txt_tasks.process_txt_file')
def process_txt_file(file_path: str, file_name: str, event: str):
    """
    Celery task wrapper для TXT парсера.
    
    Args:
        file_path: Полный путь к файлу
        file_name: Имя файла
        event: Тип события (created, modified)
    
    Returns:
        dict: Результат обработки с метаданными
    """
    
    # 1. Parse (3-stage pipeline)
    parse_result = txt_parser.parse(file_path)
    
    # 2. Save (MarkdownWriter)
    save_result = markdown_writer.save(
        parse_result=parse_result,
        file_name=file_name,
        timestamp=generate_timestamp()
    )
    
    # 3. Return unified result
    return {
        'status': 'success',
        'file_path': file_path,
        'markdown_file': save_result['file_name'],
        'markdown_path': save_result['file_path'],
        'processing_time_sec': duration,
        'metadata': parse_result['metadata']
    }
```

### RabbitMQ Queue

```
Queue: celery (default)
Routing Key: tasks.txt_tasks.process_txt_file
Priority: Normal (same as PDF/Word)
```

---

## 📈 Monitoring

### Grafana Queries

```logql
# TXT processing logs
{service="document-processors"} |= "txt-parser"

# Encoding detection
{service="document-processors"} |= "Detected encoding"

# Low confidence warnings
{service="document-processors"} |= "Low encoding confidence"

# Processing times
{service="document-processors"} |= "TXT processed successfully" 
  | regexp "duration=(?P<duration>[0-9.]+)s"
  | line_format "{{.duration}}"
```

### Key Metrics

- **Throughput:** Files processed per second
- **Latency:** Average processing time (target: <20ms)
- **Encoding distribution:** UTF-8 vs Windows-1251 vs others
- **Confidence:** Average chardet confidence scores
- **Errors:** Failed encodings, retries

---

## 🚨 Error Handling

### Error Flow

```
File Read Error
    ↓
Try with detected encoding
    ↓ FAIL
Try with UTF-8 fallback
    ↓ FAIL
Try with Windows-1251 fallback
    ↓ FAIL
Return error status
    └─ Log: [ERROR] All encoding attempts failed
```

### Retry Strategy

```python
# Celery retry configuration
@app.task(
    bind=True,
    autoretry_for=(UnicodeDecodeError, IOError),
    retry_kwargs={'max_retries': 3, 'countdown': 5},
    retry_backoff=True
)
```

---

## 📚 Related Documentation

- **README.md** - Complete TXT parser documentation
- **../MARKDOWN_WRITER.md** - Centralized save module
- **../COMPARISON.md** - PDF vs Word vs TXT comparison
- **../word/PROCESS_FLOW.md** - Word parser 7-stage pipeline
- **../pdf/PROCESS_FLOW.md** - PDF parser 5-stage pipeline

---

**Version:** 1.0.0  
**Last Updated:** 2025-10-28  
**Author:** ALPACA Development Team
