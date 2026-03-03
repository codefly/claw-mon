ALTER TABLE session_enrichment ADD COLUMN content_hash TEXT;
ALTER TABLE session_enrichment ADD COLUMN estimated_cost_usd REAL NOT NULL DEFAULT 0.0;
CREATE INDEX IF NOT EXISTS idx_session_enrichment_content_hash ON session_enrichment(content_hash);
