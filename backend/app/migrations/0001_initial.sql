CREATE TABLE IF NOT EXISTS agents (
    id TEXT PRIMARY KEY,
    first_seen_at TEXT,
    last_seen_at TEXT
);

CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL,
    file_path TEXT NOT NULL UNIQUE,
    started_at TEXT,
    ended_at TEXT,
    last_ingested_at TEXT,
    FOREIGN KEY (agent_id) REFERENCES agents(id) ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS raw_events (
    event_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    event_type TEXT NOT NULL,
    role TEXT,
    raw_json TEXT NOT NULL,
    raw_line_hash TEXT NOT NULL UNIQUE,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE ON UPDATE CASCADE,
    FOREIGN KEY (agent_id) REFERENCES agents(id) ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS usage_events (
    event_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    model TEXT NOT NULL,
    provider TEXT NOT NULL,
    input_tokens INTEGER NOT NULL CHECK (input_tokens >= 0),
    output_tokens INTEGER NOT NULL CHECK (output_tokens >= 0),
    cache_read_tokens INTEGER NOT NULL DEFAULT 0 CHECK (cache_read_tokens >= 0),
    cache_write_tokens INTEGER NOT NULL DEFAULT 0 CHECK (cache_write_tokens >= 0),
    total_tokens INTEGER NOT NULL CHECK (total_tokens >= 0),
    usd_cost REAL NOT NULL CHECK (usd_cost >= 0),
    FOREIGN KEY (event_id) REFERENCES raw_events(event_id) ON DELETE CASCADE ON UPDATE CASCADE,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE ON UPDATE CASCADE,
    FOREIGN KEY (agent_id) REFERENCES agents(id) ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS file_offsets (
    file_path TEXT PRIMARY KEY,
    inode TEXT NOT NULL,
    offset_bytes INTEGER NOT NULL CHECK (offset_bytes >= 0),
    last_size INTEGER NOT NULL CHECK (last_size >= 0),
    last_mtime REAL NOT NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS session_enrichment (
    session_id TEXT PRIMARY KEY,
    primary_category TEXT NOT NULL,
    secondary_categories TEXT NOT NULL DEFAULT '[]',
    summary TEXT,
    confidence REAL CHECK (confidence >= 0 AND confidence <= 1),
    model_used TEXT,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    job_type TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('queued', 'running', 'completed', 'failed')),
    requested_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    started_at TEXT,
    finished_at TEXT,
    progress_json TEXT NOT NULL DEFAULT '{}',
    error TEXT
);

CREATE INDEX IF NOT EXISTS idx_sessions_agent_id ON sessions(agent_id);
CREATE INDEX IF NOT EXISTS idx_raw_events_timestamp ON raw_events(timestamp);
CREATE INDEX IF NOT EXISTS idx_raw_events_session_timestamp ON raw_events(session_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_raw_events_type_role_timestamp ON raw_events(event_type, role, timestamp);
CREATE INDEX IF NOT EXISTS idx_usage_events_timestamp ON usage_events(timestamp);
CREATE INDEX IF NOT EXISTS idx_usage_events_agent_timestamp ON usage_events(agent_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_usage_events_model_timestamp ON usage_events(model, timestamp);
CREATE INDEX IF NOT EXISTS idx_usage_events_session_id ON usage_events(session_id);
CREATE INDEX IF NOT EXISTS idx_jobs_status_requested_at ON jobs(status, requested_at);
