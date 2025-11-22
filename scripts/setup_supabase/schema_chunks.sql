-- Enable the pgvector extension to work with embedding vectors
CREATE EXTENSION IF NOT EXISTS vector;

-- Create a table to store your documents
CREATE TABLE public.chunks (
    id bigserial PRIMARY KEY,
    content text, -- corresponds to Document.pageContent
    metadata jsonb, -- corresponds to Document.metadata
    embedding vector(1024) -- 1024 works for bge-m3 embeddings
);

ALTER TABLE public.chunks OWNER TO postgres;

-- Indexes for metadata queries
CREATE INDEX idx_chunks_file_hash ON public.chunks USING btree (((metadata ->> 'file_hash'::text)));
CREATE INDEX idx_chunks_file_path ON public.chunks USING btree (((metadata ->> 'file_path'::text)));

-- Vector similarity search index (using HNSW for fast approximate nearest neighbor search)
CREATE INDEX idx_chunks_embedding ON public.chunks USING hnsw (embedding vector_cosine_ops);

-- Create a function to search for documents
CREATE FUNCTION match_chunks (
    query_embedding vector(1024),
    match_count int DEFAULT NULL,
    filter jsonb DEFAULT '{}'
) RETURNS TABLE (
    id bigint,
    content text,
    metadata jsonb,
    similarity float
)
LANGUAGE plpgsql
AS $$
#variable_conflict use_column
BEGIN
    RETURN QUERY
    SELECT
        id,
        content,
        metadata,
        1 - (chunks.embedding <=> query_embedding) AS similarity
    FROM chunks
    WHERE metadata @> filter
    ORDER BY chunks.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

COMMENT ON TABLE public.chunks IS 'Хранит документы с векторными представлениями для RAG';
COMMENT ON COLUMN public.chunks.content IS 'Текстовое содержимое чанка документа';
COMMENT ON COLUMN public.chunks.metadata IS 'Метаданные: file_path, file_hash, chunk_index, timestamp и т.д.';
COMMENT ON COLUMN public.chunks.embedding IS 'Векторное представление контента (1024 измерения для bge-m3)';
COMMENT ON FUNCTION match_chunks IS 'Поиск похожих документов по векторному представлению с фильтрацией по метаданным';
