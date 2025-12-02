"""
Smart chunker с использованием LangChain.

Возможности:
- Рекурсивное разбиение с учётом структуры текста
- Перекрытие (overlap) для сохранения контекста
- Сохранение целостности таблиц и блоков кода
- Умные разделители (параграфы → предложения → слова)
"""
from typing import List, Optional
from utils.logging import get_logger
from core.domain.files.models import FileSnapshot

logger = get_logger("core.chunker.smart")

# Настройки по умолчанию
DEFAULT_CHUNK_SIZE = 1000
DEFAULT_CHUNK_OVERLAP = 200

# Паттерны для сохранения целостности структурных блоков
TABLE_MARKERS = [
    "|",      # Markdown таблицы
    "┌", "├", "└", "│",  # Unicode box drawing
    "+--", "---+",  # ASCII таблицы
]

CODE_BLOCK_MARKERS = ["```", "~~~"]


def _is_table_line(line: str) -> bool:
    """Проверяет, является ли строка частью таблицы"""
    stripped = line.strip()
    return any(marker in stripped for marker in TABLE_MARKERS)


def _extract_protected_blocks(text: str) -> tuple[str, dict[str, str]]:
    """
    Извлекает защищённые блоки (таблицы, код) и заменяет их плейсхолдерами.
    
    Returns:
        tuple: (текст с плейсхолдерами, словарь {плейсхолдер: оригинальный блок})
    """
    protected = {}
    result_lines = []
    
    lines = text.split('\n')
    i = 0
    block_counter = 0
    
    while i < len(lines):
        line = lines[i]
        
        # Проверяем блок кода
        if any(line.strip().startswith(marker) for marker in CODE_BLOCK_MARKERS):
            block_lines = [line]
            marker = line.strip()[:3]
            i += 1
            while i < len(lines) and not lines[i].strip().startswith(marker):
                block_lines.append(lines[i])
                i += 1
            if i < len(lines):
                block_lines.append(lines[i])
                i += 1
            
            placeholder = f"__PROTECTED_BLOCK_{block_counter}__"
            protected[placeholder] = '\n'.join(block_lines)
            result_lines.append(placeholder)
            block_counter += 1
            continue
        
        # Проверяем таблицу
        if _is_table_line(line):
            table_lines = [line]
            i += 1
            while i < len(lines) and (_is_table_line(lines[i]) or lines[i].strip() == ""):
                if lines[i].strip():  # Пропускаем пустые строки внутри таблицы
                    table_lines.append(lines[i])
                i += 1
            
            placeholder = f"__PROTECTED_BLOCK_{block_counter}__"
            protected[placeholder] = '\n'.join(table_lines)
            result_lines.append(placeholder)
            block_counter += 1
            continue
        
        result_lines.append(line)
        i += 1
    
    return '\n'.join(result_lines), protected


def _restore_protected_blocks(chunks: List[str], protected: dict[str, str]) -> List[str]:
    """Восстанавливает защищённые блоки в чанках"""
    restored = []
    for chunk in chunks:
        for placeholder, original in protected.items():
            chunk = chunk.replace(placeholder, original)
        restored.append(chunk)
    return restored


def smart_chunking(
    file: FileSnapshot,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
    preserve_tables: bool = True,
) -> List[str]:
    """
    Умное разбиение текста на чанки с использованием LangChain.
    
    Args:
        file: FileSnapshot с заполненным raw_text
        chunk_size: Максимальный размер чанка в символах
        chunk_overlap: Размер перекрытия между чанками
        preserve_tables: Сохранять таблицы целиком (не разбивать)
        
    Returns:
        List[str]: Список чанков с перекрытием
    """
    try:
        from langchain_text_splitters import RecursiveCharacterTextSplitter
    except ImportError:
        logger.warning("langchain-text-splitters not installed, falling back to simple chunking")
        from .simple_chunker import chunking
        return chunking(file)
    
    text = file.raw_text or ""
    if not text.strip():
        logger.warning(f"Empty text for chunking | file={file.path}")
        return []
    
    logger.info(f"🔪 Smart chunking: {file.path} | size={chunk_size} overlap={chunk_overlap}")
    
    # Защищаем таблицы и код от разбиения
    protected_blocks = {}
    if preserve_tables:
        text, protected_blocks = _extract_protected_blocks(text)
        if protected_blocks:
            logger.debug(f"Protected {len(protected_blocks)} blocks from splitting")
    
    # Иерархия разделителей: от крупных к мелким
    # LangChain будет пробовать разделить по ним в порядке приоритета
    separators = [
        "\n\n\n",      # Разделы документа
        "\n\n",        # Параграфы
        "\n",          # Строки
        ". ",          # Предложения
        "! ",
        "? ",
        "; ",          # Части предложений  
        ", ",
        " ",           # Слова
        "",            # Символы (крайний случай)
    ]
    
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=separators,
        length_function=len,
        is_separator_regex=False,
        keep_separator=True,  # Сохраняем разделители в начале чанков
    )
    
    try:
        chunks = splitter.split_text(text)
    except Exception as e:
        logger.error(f"LangChain splitter failed | file={file.path} error={e}")
        # Fallback на простой чанкер
        from .simple_chunker import chunking
        return chunking(file)
    
    # Восстанавливаем защищённые блоки
    if protected_blocks:
        chunks = _restore_protected_blocks(chunks, protected_blocks)
    
    # Фильтруем пустые чанки
    chunks = [c.strip() for c in chunks if c.strip()]
    
    # Объединяем маленькие чанки с защищёнными блоками
    # Если защищённый блок превышает chunk_size, оставляем его целиком
    final_chunks = []
    for chunk in chunks:
        if chunk:
            final_chunks.append(chunk)
    
    logger.info(f"✅ Smart chunking complete | file={file.path} chunks={len(final_chunks)}")
    
    return final_chunks


# Алиас для совместимости с интерфейсом Chunker
def chunking(file: FileSnapshot) -> List[str]:
    """Wrapper для совместимости с контрактом Chunker"""
    return smart_chunking(file)
