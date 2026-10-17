-- Safe to run more than once. Apply it to your running database (see the steps).

CREATE TABLE IF NOT EXISTS ingestion_watermark (
  source TEXT PRIMARY KEY,
  last_fetched_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS papers (
  paper_key TEXT PRIMARY KEY,
  arxiv_id TEXT NOT NULL,
  version INT NOT NULL,
  title TEXT,
  authors JSONB,
  abstract TEXT,
  published_at TIMESTAMPTZ,
  updated_at TIMESTAMPTZ,
  bronze_pdf_path TEXT,
  bronze_json_path TEXT,
  status TEXT DEFAULT 'ingested',  -- ingested | parsed | embedded | failed
  ingested_at TIMESTAMPTZ DEFAULT now()
);