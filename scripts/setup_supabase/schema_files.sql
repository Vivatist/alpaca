-- ENUM тип для статусов синхронизации
CREATE TYPE public.status_sync AS ENUM (
    'ok',
    'added',
    'deleted',
    'updated',
    'processed',
    'error'
);

ALTER TYPE public.status_sync OWNER TO postgres;

COMMENT ON TYPE public.status_sync IS 'Статусы синхронизации';

-- File state table для отслеживания состояния файлов
CREATE TABLE public.files (
    id integer NOT NULL,
    path text NOT NULL,
    size bigint NOT NULL,
    last_checked timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    hash text NOT NULL,
    mtime double precision,
    status_sync public.status_sync,
    raw_text text
);

ALTER TABLE public.files OWNER TO postgres;

-- Sequence for files ID
CREATE SEQUENCE public.files_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER TABLE public.files_id_seq OWNER TO postgres;
ALTER SEQUENCE public.files_id_seq OWNED BY public.files.id;
ALTER TABLE ONLY public.files ALTER COLUMN id SET DEFAULT nextval('public.files_id_seq'::regclass);

-- Constraints
ALTER TABLE ONLY public.files
    ADD CONSTRAINT files_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.files
    ADD CONSTRAINT files_path_key UNIQUE (path);

-- Indexes для быстрого поиска
CREATE INDEX idx_hash ON public.files USING btree (hash);
CREATE INDEX idx_file_path ON public.files USING btree (file_path);
CREATE INDEX idx_status_mtime ON public.files USING btree (status_sync, file_mtime DESC);

COMMENT ON TABLE public.files IS 'Отслеживает состояние файлов в системе';
COMMENT ON COLUMN public.files.file_path IS 'Абсолютный путь к файлу';
COMMENT ON COLUMN public.files.file_hash IS 'SHA256 хеш содержимого файла';
COMMENT ON COLUMN public.files.file_mtime IS 'Время последней модификации файла (unix timestamp)';
COMMENT ON COLUMN public.files.status_sync IS 'Статус синхронизации: ok/added/deleted/updated/processed/error';
COMMENT ON COLUMN public.files.raw_text IS 'Необработанный текст из файла (опционально)';
