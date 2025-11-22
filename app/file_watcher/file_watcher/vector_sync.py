"""Модуль для синхронизации таблиц file_state и chunks

Сравнивает состояние файлов в file_state с векторной базой chunks
и устанавливает значение status_sync для каждого файла:
- 'ok': файл синхронизирован (хэш совпадает)
- 'added': файл есть в file_state, но отсутствует в chunks
- 'updated': файл есть в обеих таблицах, но хэши различаются
- 'deleted': файл есть в chunks, но отсутствует в file_state

ВАЖНО: Модуль НЕ изменяет таблицу chunks, только обновляет status_sync в file_state.
Фактическое удаление/добавление в векторную БД выполняет другой flow.
"""

import logging
from typing import Dict

logger = logging.getLogger(__name__)


class VectorSync:
    """Класс для синхронизации file_state и chunks через сравнение хэшей"""
    
    def __init__(self, db):
        """
        Args:
            db: Экземпляр класса Database
        """
        self.db = db
    
    def sync_status(self) -> Dict[str, int]:
        """Сравнивает file_state с documents и обновляет status_sync
        
        Алгоритм:
        1. Получает все хэши и пути из file_state
        2. Получает все уникальные хэши и пути из documents (группируя чанки)
        3. Сравнивает и определяет статус каждого файла:
           - Хэш совпадает → status_sync = 'ok'
           - Файл только в file_state → status_sync = 'added'
           - Файл в обеих, но хэш разный → status_sync = 'updated'
           - Файл только в documents → ничего (файл удалён с диска, но остался в БД)
        4. Обновляет status_sync в file_state
        
        Returns:
            dict: Статистика операций
                - ok: количество синхронизированных файлов
                - added: количество новых файлов
                - updated: количество изменённых файлов
                - unchanged: количество файлов без изменений статуса
        """
        stats = {
            'ok': 0,
            'added': 0,
            'updated': 0,
            'unchanged': 0
        }
        
        # 1. Получаем все файлы из file_state
        file_state_records = self.db.get_file_state_records()
        
        # 2. Получаем все уникальные файлы из documents
        documents_records = self.db.get_documents_records()
        
        # Создаём словари для быстрого поиска
        # file_state: path -> (hash, current_status)
        file_state_map = {
            row[0]: {'hash': row[1], 'status': row[2]} 
            for row in file_state_records
        }
        
        # documents: path -> hash
        documents_map = {row[1]: row[0] for row in documents_records}
        
        # documents: hash -> path (для обратного поиска)
        documents_hash_map = {row[0]: row[1] for row in documents_records}
        
        # 3. Определяем новый статус для каждого файла в file_state
        updates = []  # [(new_status, file_path), ...]
        
        for file_path, file_info in file_state_map.items():
            file_hash = file_info['hash']
            current_status = file_info['status']
            
            # ВАЖНО: файлы со статусами 'deleted', 'updated', 'processed', 'error' не трогаем
            # Они должны быть обработаны main-loop или вручную:
            # 'deleted' - будут удалены из documents
            # 'updated' - будут обновлены в documents
            # 'processed' - обрабатываются прямо сейчас, не трогаем!
            # 'error' - ошибка обработки, сбрасывается только вручную
            if current_status in ('deleted', 'updated', 'processed', 'error'):
                stats['unchanged'] += 1
                continue
            
            new_status = None
            
            if file_path in documents_map:
                # Файл есть в documents
                doc_hash = documents_map[file_path]
                
                if doc_hash == file_hash:
                    # Хэши совпадают - всё синхронизировано
                    new_status = 'ok'
                else:
                    # Хэши разные - файл обновлён на диске
                    new_status = 'updated'
            else:
                # Файла нет в documents
                if file_hash in documents_hash_map:
                    # Хэш существует, но с другим путём (переименование?)
                    # Считаем это обновлением
                    new_status = 'updated'
                else:
                    # Файла вообще нет в documents - новый файл
                    new_status = 'added'
            
            # Обновляем только если статус изменился
            if new_status != current_status:
                updates.append((new_status, file_path))
                stats[new_status] += 1
            else:
                stats['unchanged'] += 1
        
        # 4. Выполняем массовое обновление status_sync
        if updates:
            self.db.update_status_sync_batch(updates)
            logger.info(
                f"Updated status_sync for {len(updates)} files: "
                f"ok={stats['ok']}, added={stats['added']}, updated={stats['updated']}"
            )
        
        # 5. Опционально: находим файлы, которые есть в documents, но нет в file_state
        # Эти файлы были удалены с диска, но остались в векторной БД
        # Их должен будет обработать main-loop (удалить из documents)
        orphaned_paths = set(documents_map.keys()) - set(file_state_map.keys())
        if orphaned_paths:
            logger.warning(
                f"Found {len(orphaned_paths)} orphaned documents "
                f"(not in file_state): {list(orphaned_paths)[:5]}..."
            )
        
        return stats
