-- Миграция: Переименование колонок таблицы files
-- Убираем префикс "file_" для упрощения работы с Pydantic моделями
-- Дата: 2025-11-28

BEGIN;

-- Переименовываем колонки
ALTER TABLE public.files RENAME COLUMN file_path TO path;
ALTER TABLE public.files RENAME COLUMN file_hash TO hash;
ALTER TABLE public.files RENAME COLUMN file_size TO size;
ALTER TABLE public.files RENAME COLUMN file_mtime TO mtime;

-- Обновляем constraint для path
ALTER TABLE public.files DROP CONSTRAINT IF EXISTS files_file_path_key;
ALTER TABLE public.files ADD CONSTRAINT files_path_key UNIQUE (path);

-- Пересоздаём индекс для hash
DROP INDEX IF EXISTS idx_file_hash;
CREATE INDEX idx_hash ON public.files USING btree (hash);

-- Проверяем что всё применилось
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'files' AND column_name = 'path'
    ) THEN
        RAISE EXCEPTION 'Миграция не применилась: колонка path не найдена';
    END IF;
    
    RAISE NOTICE 'Миграция успешно применена';
END $$;

COMMIT;
