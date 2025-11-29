#!/usr/bin/env python3
"""
Table Parser - парсинг сложных таблиц из PDF

Специализированный парсер для документов с таблицами.
Использует camelot-py и tabula-py для максимальной точности.
"""

import os
from typing import List, Dict, Any

try:
    import camelot
    CAMELOT_AVAILABLE = True
except ImportError:
    CAMELOT_AVAILABLE = False

try:
    import tabula
    TABULA_AVAILABLE = True
except ImportError:
    TABULA_AVAILABLE = False

try:
    import fitz  # PyMuPDF для детекции поворота
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False

from utils.logging import get_logger

logger = get_logger("alpaca.parser.pdf_table_parser")


def detect_rotation(file_path: str) -> int:
    """
    Определяет угол поворота страниц PDF
    
    Args:
        file_path: Путь к PDF файлу
        
    Returns:
        Угол поворота (0, 90, 180, 270)
    """
    if not PYMUPDF_AVAILABLE:
        return 0
    
    try:
        doc = fitz.open(file_path)
        rotations = [page.rotation for page in doc]
        doc.close()
        
        # Возвращаем наиболее частый угол поворота
        if rotations:
            return max(set(rotations), key=rotations.count)
        return 0
    except Exception as e:
        logger.warning(f"Не удалось определить поворот | file={file_path} error={e}")
        return 0


def fix_rotation(file_path: str, output_path: str = None) -> str:
    """
    Исправляет поворот страниц PDF
    
    Args:
        file_path: Путь к исходному PDF
        output_path: Путь для сохранения (если None, перезаписывает исходный)
        
    Returns:
        Путь к исправленному файлу
    """
    if not PYMUPDF_AVAILABLE:
        return file_path
    
    try:
        doc = fitz.open(file_path)
        rotated = False
        
        for page in doc:
            if page.rotation != 0:
                page.set_rotation(0)
                rotated = True
        
        if rotated:
            if output_path is None:
                output_path = file_path.replace('.pdf', '_rotated.pdf')
            doc.save(output_path)
            logger.info(f"✅ Поворот исправлен | file={output_path}")
            doc.close()
            return output_path
        
        doc.close()
        return file_path
    except Exception as e:
        logger.error(f"❌ Ошибка исправления поворота | file={file_path} error={e}")
        return file_path


def parse_tables_with_camelot(file_path: str, flavor: str = 'lattice') -> List[Dict[str, Any]]:
    """
    Парсинг таблиц через camelot-py
    
    Args:
        file_path: Путь к PDF файлу
        flavor: 'lattice' (с границами) или 'stream' (без границ)
        
    Returns:
        Список таблиц в формате {page, data, text}
    """
    if not CAMELOT_AVAILABLE:
        logger.warning("camelot-py не установлен")
        return []
    
    try:
        # Попытка парсинга с выбранным flavor
        if flavor == 'lattice':
            tables = camelot.read_pdf(
                file_path,
                flavor='lattice',
                pages='all',
                suppress_stdout=True
            )
        else:  # stream
            tables = camelot.read_pdf(
                file_path,
                flavor='stream',
                pages='all',
                edge_tol=50,
                row_tol=10,
                suppress_stdout=True
            )
        
        result = []
        for i, table in enumerate(tables):
            # Конвертируем в текст
            text = table.df.to_string(index=False, header=True)
            result.append({
                'page': table.page,
                'data': table.df.to_dict('records'),
                'text': text,
                'accuracy': table.accuracy if hasattr(table, 'accuracy') else 0
            })
        
        logger.info(f"📊 Camelot извлек таблиц | file={file_path} count={len(result)} flavor={flavor}")
        return result
        
    except Exception as e:
        logger.error(f"❌ Ошибка Camelot | file={file_path} flavor={flavor} error={e}")
        return []


def parse_tables_with_tabula(file_path: str) -> List[Dict[str, Any]]:
    """
    Парсинг таблиц через tabula-py
    
    Args:
        file_path: Путь к PDF файлу
        
    Returns:
        Список таблиц в формате {page, data, text}
    """
    if not TABULA_AVAILABLE:
        logger.warning("tabula-py не установлен")
        return []
    
    try:
        # Пытаемся сначала с lattice (более точно для таблиц с линиями)
        tables = tabula.read_pdf(
            file_path,
            pages='all',
            multiple_tables=True,
            lattice=True,
            pandas_options={'header': None}
        )
        
        result = []
        for i, df in enumerate(tables):
            if df.empty:
                continue
            
            text = df.to_string(index=False, header=False)
            result.append({
                'page': i + 1,  # tabula не возвращает номер страницы
                'data': df.to_dict('records'),
                'text': text
            })
        
        logger.info(f"📊 Tabula извлекла таблиц | file={file_path} count={len(result)}")
        return result
        
    except Exception as e:
        logger.error(f"❌ Ошибка Tabula | file={file_path} error={e}")
        return []


def parse_pdf_tables(file_path: str, auto_rotate: bool = True) -> str:
    """
    Комплексный парсинг PDF с таблицами
    
    Стратегия:
    1. Детекция и исправление поворота (если auto_rotate=True)
    2. Попытка через camelot (lattice)
    3. Попытка через camelot (stream)
    4. Попытка через tabula
    5. Объединение результатов
    
    Args:
        file_path: Путь к PDF файлу
        auto_rotate: Автоматически исправлять поворот
        
    Returns:
        Текст с таблицами
    """
    logger.info(f"📊 Начало парсинга таблиц | file={file_path}")
    
    # Шаг 1: Исправление поворота
    working_file = file_path
    if auto_rotate:
        rotation = detect_rotation(file_path)
        if rotation != 0:
            logger.info(f"🔄 Обнаружен поворот {rotation}° | file={file_path}")
            working_file = fix_rotation(file_path)
    
    # Шаг 2-4: Попытки парсинга
    all_tables = []
    
    # Camelot lattice (для таблиц с границами)
    camelot_lattice = parse_tables_with_camelot(working_file, flavor='lattice')
    if camelot_lattice:
        all_tables.extend(camelot_lattice)
    else:
        # Camelot stream (для таблиц без границ)
        camelot_stream = parse_tables_with_camelot(working_file, flavor='stream')
        if camelot_stream:
            all_tables.extend(camelot_stream)
    
    # Tabula как дополнительный источник
    tabula_tables = parse_tables_with_tabula(working_file)
    if tabula_tables:
        all_tables.extend(tabula_tables)
    
    # Шаг 5: Объединение результатов
    if not all_tables:
        logger.warning(f"⚠️ Таблицы не найдены | file={file_path}")
        return ""
    
    # Удаляем дубликаты и сортируем по страницам
    unique_tables = {}
    for table in all_tables:
        page = table['page']
        text = table['text']
        accuracy = table.get('accuracy', 0)
        
        # Оставляем таблицу с лучшей точностью для каждой страницы
        if page not in unique_tables or accuracy > unique_tables[page].get('accuracy', 0):
            unique_tables[page] = table
    
    # Формируем финальный текст
    result_parts = []
    for page in sorted(unique_tables.keys()):
        table = unique_tables[page]
        result_parts.append(f"\n## Страница {page}\n")
        result_parts.append(table['text'])
    
    result = "\n".join(result_parts)
    
    # Удаляем временный файл с исправленным поворотом
    if working_file != file_path and os.path.exists(working_file):
        try:
            os.remove(working_file)
        except:
            pass
    
    logger.info(f"✅ Парсинг таблиц завершен | file={file_path} tables={len(unique_tables)}")
    return result
