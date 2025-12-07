#!/usr/bin/env python3
"""
Document Converter - конвертация старых офисных форматов

Сейчас поддерживает:
- .doc → .docx
- .ppt → .pptx
"""

import os
import tempfile
import subprocess
from pathlib import Path
from typing import Optional

from logging_config import get_logger

logger = get_logger("core.parser.document_converter")


def convert_doc_to_docx(doc_path: str) -> Optional[str]:
    """Конвертация .doc в .docx через LibreOffice headless"""
    return _convert_with_libreoffice(
        source_path=doc_path,
        target_ext="docx",
        temp_prefix="alpaca_doc_convert_",
        log_label=".doc → .docx",
    )


def convert_ppt_to_pptx(ppt_path: str) -> Optional[str]:
    """Конвертация .ppt в .pptx через LibreOffice headless"""
    return _convert_with_libreoffice(
        source_path=ppt_path,
        target_ext="pptx",
        temp_prefix="alpaca_ppt_convert_",
        log_label=".ppt → .pptx",
    )


def _convert_with_libreoffice(
    source_path: str,
    target_ext: str,
    temp_prefix: str,
    log_label: str,
) -> Optional[str]:
    """Общая функция конвертации через LibreOffice"""
    try:
        # Создаем временную директорию для конвертированного файла
        temp_dir = tempfile.mkdtemp(prefix=temp_prefix)
        logger.info(
            f"Converting {log_label} via LibreOffice | source={source_path} temp_dir={temp_dir}"
        )
        
        # Запускаем LibreOffice в headless режиме
        result = subprocess.run(
            [
                'libreoffice',
                '--headless',
                '--convert-to', target_ext,
                '--outdir', temp_dir,
                source_path
            ],
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode != 0:
            logger.error(f"LibreOffice conversion failed (returncode={result.returncode} stderr={result.stderr})")
            return None
        
        # Проверяем что файл создан
        doc_filename = Path(source_path).stem
        converted_file = Path(temp_dir) / f"{doc_filename}.{target_ext}"
        
        if converted_file.exists():
            logger.info(f"Conversion successful (output={converted_file} size={converted_file.stat().st_size})")
            return str(converted_file)
        else:
            logger.error(f"Converted file not found (expected={converted_file})")
            return None
            
    except subprocess.TimeoutExpired:
        logger.error(f"LibreOffice conversion timeout (file={source_path} limit=60s)")
        return None
    except Exception as e:
        logger.error(f"Conversion error (file={source_path} error={type(e).__name__}: {e})")
        return None
