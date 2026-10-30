-- Run once after the first embedding load. Building the index on a full table is faster
-- than maintaining it row by row, and \timing shows the build time for your metrics.
\timing on
CREATE INDEX IF NOT EXISTS chunks_hnsw_idx ON chunks
  USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);