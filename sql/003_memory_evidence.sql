PRAGMA foreign_keys=ON;

ALTER TABLE proposals ADD COLUMN retrieval_event_id TEXT;

CREATE TABLE IF NOT EXISTS memory_records (
    memory_id TEXT PRIMARY KEY,
    campaign_id TEXT,
    comparability_group TEXT,
    record_type TEXT NOT NULL,
    source_kind TEXT NOT NULL,
    source_ref TEXT NOT NULL,
    family TEXT,
    lane TEXT,
    eval_split TEXT,
    outcome_label TEXT,
    title TEXT NOT NULL,
    summary TEXT NOT NULL,
    tags_json TEXT NOT NULL DEFAULT '[]',
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS retrieval_events (
    retrieval_event_id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL,
    proposal_id TEXT,
    family TEXT,
    lane TEXT,
    query_text TEXT NOT NULL,
    query_tags_json TEXT NOT NULL DEFAULT '[]',
    query_payload_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    FOREIGN KEY (proposal_id) REFERENCES proposals(proposal_id)
);

CREATE TABLE IF NOT EXISTS retrieval_event_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    retrieval_event_id TEXT NOT NULL,
    memory_id TEXT NOT NULL,
    rank INTEGER NOT NULL,
    score REAL NOT NULL,
    selected_for_context INTEGER NOT NULL DEFAULT 0,
    role_hint TEXT,
    reason TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (retrieval_event_id) REFERENCES retrieval_events(retrieval_event_id),
    FOREIGN KEY (memory_id) REFERENCES memory_records(memory_id)
);

CREATE TABLE IF NOT EXISTS proposal_evidence_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    proposal_id TEXT NOT NULL,
    memory_id TEXT NOT NULL,
    retrieval_event_id TEXT,
    role TEXT NOT NULL,
    score REAL,
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (proposal_id) REFERENCES proposals(proposal_id),
    FOREIGN KEY (memory_id) REFERENCES memory_records(memory_id),
    FOREIGN KEY (retrieval_event_id) REFERENCES retrieval_events(retrieval_event_id)
);

CREATE INDEX IF NOT EXISTS idx_memory_records_campaign_type
    ON memory_records(campaign_id, record_type, outcome_label);

CREATE INDEX IF NOT EXISTS idx_memory_records_comparability
    ON memory_records(comparability_group, record_type);

CREATE INDEX IF NOT EXISTS idx_retrieval_events_campaign
    ON retrieval_events(campaign_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_retrieval_event_items_event_rank
    ON retrieval_event_items(retrieval_event_id, rank);

CREATE INDEX IF NOT EXISTS idx_proposal_evidence_links_proposal
    ON proposal_evidence_links(proposal_id);

INSERT OR IGNORE INTO schema_migrations(version, applied_at)
VALUES ('003_memory_evidence', CURRENT_TIMESTAMP);
