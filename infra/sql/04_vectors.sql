-- Vector store for the validated chunks (gold layer). Safe to run more than once.
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS chunks (
  chunk_id         TEXT PRIMARY KEY,
  paper_key        TEXT NOT NULL,
  arxiv_id         TEXT NOT NULL,
  version          INT  NOT NULL,
  title            TEXT NOT NULL,
  section          TEXT,
  published_at     TIMESTAMPTZ,
  chunk_index      INT  NOT NULL,
  text             TEXT NOT NULL,
  text_hash        TEXT NOT NULL,
  n_words          INT,
  bronze_pdf_path  TEXT,
  chunk_strategy   TEXT,
  pipeline_version TEXT NOT NULL,
  embedding        vector(384) NOT NULL,
  embedding_model  TEXT NOT NULL,
  embed_key        TEXT NOT NULL,   -- hash of model + the exact text that was embedded (the cache key)
  is_deleted       BOOLEAN NOT NULL DEFAULT FALSE,
  tsv              tsvector GENERATED ALWAYS AS (to_tsvector('english', text)) STORED,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS chunks_paper_idx   ON chunks (paper_key);
CREATE INDEX IF NOT EXISTS chunks_arxiv_idx   ON chunks (arxiv_id);
CREATE INDEX IF NOT EXISTS chunks_pub_idx     ON chunks (published_at);
CREATE INDEX IF NOT EXISTS chunks_section_idx ON chunks (section);
CREATE INDEX IF NOT EXISTS chunks_tsv_idx     ON chunks USING GIN (tsv);
-- The vector index (HNSW) is created AFTER the first load, see 05_vector_index.sql