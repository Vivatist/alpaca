-- Enable vector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Documents table for RAG
CREATE TABLE public.chunks (
    id bigint NOT NULL,
    content text,
    metadata jsonb,
    embedding public.vector(1024)
);

ALTER TABLE public.chunks OWNER TO postgres;

-- Sequence for chunks ID
CREATE SEQUENCE public.chunks_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER TABLE public.chunks_id_seq OWNER TO postgres;
ALTER SEQUENCE public.chunks_id_seq OWNED BY public.chunks.id;
ALTER TABLE ONLY public.chunks ALTER COLUMN id SET DEFAULT nextval('public.chunks_id_seq'::regclass);

-- Primary key constraint
ALTER TABLE ONLY public.chunks
    ADD CONSTRAINT chunks_pkey PRIMARY KEY (id);

-- Indexes for metadata queries
CREATE INDEX idx_chunks_file_hash ON public.chunks USING btree (((metadata ->> 'file_hash'::text)));
CREATE INDEX idx_chunks_file_path ON public.chunks USING btree (((metadata ->> 'file_path'::text)));

-- Vector similarity search index (using HNSW for fast approximate nearest neighbor search)
CREATE INDEX ON public.chunks USING hnsw (embedding vector_cosine_ops);

COMMENT ON TABLE public.chunks IS 'Хранит документы с векторными представлениями для RAG';
COMMENT ON COLUMN public.chunks.content IS 'Текстовое содержимое чанка документа';
COMMENT ON COLUMN public.chunks.metadata IS 'Метаданные: file_path, file_hash, chunk_index, timestamp и т.д.';
COMMENT ON COLUMN public.chunks.embedding IS 'Векторное представление контента (1024 измерения для bge-m3)';
