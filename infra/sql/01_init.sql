-- Separate database for Airflow's own metadata
CREATE DATABASE airflow;-- pgvector for the app database
CREATE EXTENSION IF NOT EXISTS vector;-- Incremental-load watermark (Phase 2)
CREATE TABLE IF NOT EXISTS ingestion_watermark (
source TEXT PRIMARY KEY,
last_fetched_at TIMESTAMPTZ NOT NULL
)