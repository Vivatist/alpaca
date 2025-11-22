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
CREATE TABLE public.file_state (
    id integer NOT NULL,
    file_path text NOT NULL,
    file_size bigint NOT NULL,
    last_checked timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    file_hash text NOT NULL,
    file_mtime double precision,
    status_sync public.status_sync,
    raw_text text
);

ALTER TABLE public.file_state OWNER TO postgres;

-- Sequence for file_state ID
CREATE SEQUENCE public.file_state_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER TABLE public.file_state_id_seq OWNER TO postgres;
ALTER SEQUENCE public.file_state_id_seq OWNED BY public.file_state.id;
ALTER TABLE ONLY public.file_state ALTER COLUMN id SET DEFAULT nextval('public.file_state_id_seq'::regclass);

-- Constraints
ALTER TABLE ONLY public.file_state
    ADD CONSTRAINT file_state_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.file_state
    ADD CONSTRAINT file_state_file_path_key UNIQUE (file_path);

-- Indexes для быстрого поиска
CREATE INDEX idx_file_hash ON public.file_state USING btree (file_hash);
CREATE INDEX idx_file_path ON public.file_state USING btree (file_path);
CREATE INDEX idx_status_mtime ON public.file_state USING btree (status_sync, file_mtime DESC);

COMMENT ON TABLE public.file_state IS 'Отслеживает состояние файлов в системе';
COMMENT ON COLUMN public.file_state.file_path IS 'Абсолютный путь к файлу';
COMMENT ON COLUMN public.file_state.file_hash IS 'SHA256 хеш содержимого файла';
COMMENT ON COLUMN public.file_state.file_mtime IS 'Время последней модификации файла (unix timestamp)';
COMMENT ON COLUMN public.file_state.status_sync IS 'Статус синхронизации: ok/added/deleted/updated/processed/error';
COMMENT ON COLUMN public.file_state.raw_text IS 'Необработанный текст из файла (опционально)';
