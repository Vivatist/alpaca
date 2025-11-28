#!/usr/bin/env python3
"""
Document Converter - конвертация старых форматов Word

Конвертирует .doc в .docx через LibreOffice.
"""

import os
import tempfile
import subprocess
from pathlib import Path
from typing import Optional

from utils.logging import get_logger

logger = get_logger("alpaca.parser.document_converter")


def convert_doc_to_docx(doc_path: str) -> Optional[str]:
    """
    Конвертация .doc в .docx через LibreOffice headless
    
    Args:
        doc_path: Путь к исходному .doc файлу
        
    Returns:
        Путь к сконвертированному .docx или None при ошибке
    """
    try:
        # Создаем временную директорию для конвертированного файла
        temp_dir = tempfile.mkdtemp(prefix="alpaca_doc_convert_")
        logger.info(f"Converting .doc to .docx (source={doc_path} temp_dir={temp_dir})")
        
        # Запускаем LibreOffice в headless режиме
        result = subprocess.run(
            [
                'libreoffice',
                '--headless',
                '--convert-to', 'docx',
                '--outdir', temp_dir,
                doc_path
            ],
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode != 0:
            logger.error(f"LibreOffice conversion failed (returncode={result.returncode} stderr={result.stderr})")
            return None
        
        # Проверяем что файл создан
        doc_filename = Path(doc_path).stem
        converted_file = Path(temp_dir) / f"{doc_filename}.docx"
        
        if converted_file.exists():
            logger.info(f"Conversion successful (output={converted_file} size={converted_file.stat().st_size})")
            return str(converted_file)
        else:
            logger.error(f"Converted file not found (expected={converted_file})")
            return None
            
    except subprocess.TimeoutExpired:
        logger.error(f"LibreOffice conversion timeout (file={doc_path} limit=60s)")
        return None
    except Exception as e:
        logger.error(f"Conversion error (file={doc_path} error={type(e).__name__}: {e})")
        return None
