-- Enable vector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Documents table for RAG
CREATE TABLE public.documents (
    id bigint NOT NULL,
    content text,
    metadata jsonb,
    embedding public.vector(1024)
);

ALTER TABLE public.documents OWNER TO postgres;

-- Sequence for documents ID
CREATE SEQUENCE public.documents_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER TABLE public.documents_id_seq OWNER TO postgres;
ALTER SEQUENCE public.documents_id_seq OWNED BY public.documents.id;
ALTER TABLE ONLY public.documents ALTER COLUMN id SET DEFAULT nextval('public.documents_id_seq'::regclass);

-- Primary key constraint
ALTER TABLE ONLY public.documents
    ADD CONSTRAINT documents_pkey PRIMARY KEY (id);

-- Indexes for metadata queries
CREATE INDEX idx_documents_file_hash ON public.documents USING btree (((metadata ->> 'file_hash'::text)));
CREATE INDEX idx_documents_file_path ON public.documents USING btree (((metadata ->> 'file_path'::text)));

-- Vector similarity search index (using HNSW for fast approximate nearest neighbor search)
CREATE INDEX ON public.documents USING hnsw (embedding vector_cosine_ops);

COMMENT ON TABLE public.documents IS 'Хранит документы с векторными представлениями для RAG';
COMMENT ON COLUMN public.documents.content IS 'Текстовое содержимое чанка документа';
COMMENT ON COLUMN public.documents.metadata IS 'Метаданные: file_path, file_hash, chunk_index, timestamp и т.д.';
COMMENT ON COLUMN public.documents.embedding IS 'Векторное представление контента (1024 измерения для bge-m3)';
