-- One row per validation attempt of a silver Parquet file. Safe to run more than once.
CREATE TABLE IF NOT EXISTS quality_runs (
  id SERIAL PRIMARY KEY,
  silver_key TEXT NOT NULL,
  gold_key TEXT,
  dead_letter_key TEXT,
  total INT NOT NULL,
  valid INT NOT NULL,
  invalid INT NOT NULL,
  failure_rate NUMERIC(7,4) NOT NULL,
  reasons JSONB,
  status TEXT NOT NULL,            -- passed | blocked
  ran_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS quality_runs_silver_idx ON quality_runs (silver_key);