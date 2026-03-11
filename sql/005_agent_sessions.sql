PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS agent_sessions (
    session_id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL,
    status TEXT NOT NULL,
    operator_mode TEXT NOT NULL DEFAULT 'agent',
    started_at TEXT NOT NULL,
    ended_at TEXT,
    hours_budget REAL,
    max_runs_budget INTEGER,
    max_structured_runs_budget INTEGER,
    max_code_runs_budget INTEGER,
    allow_confirm INTEGER NOT NULL DEFAULT 0,
    seed_policy TEXT NOT NULL,
    backend TEXT,
    device_profile TEXT,
    queue_refills INTEGER NOT NULL DEFAULT 0,
    run_count INTEGER NOT NULL DEFAULT 0,
    structured_run_count INTEGER NOT NULL DEFAULT 0,
    code_run_count INTEGER NOT NULL DEFAULT 0,
    confirm_run_count INTEGER NOT NULL DEFAULT 0,
    validation_review_count INTEGER NOT NULL DEFAULT 0,
    report_checkpoint_count INTEGER NOT NULL DEFAULT 0,
    self_review_count INTEGER NOT NULL DEFAULT 0,
    lane_switch_count INTEGER NOT NULL DEFAULT 0,
    last_lane TEXT,
    stop_reason TEXT,
    session_manifest_path TEXT,
    retrospective_json_path TEXT,
    report_json_path TEXT,
    session_summary_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (campaign_id) REFERENCES campaigns(campaign_id)
);

CREATE TABLE IF NOT EXISTS agent_session_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    lane TEXT,
    proposal_id TEXT,
    experiment_id TEXT,
    review_id TEXT,
    report_path TEXT,
    payload_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES agent_sessions(session_id)
);

CREATE INDEX IF NOT EXISTS idx_agent_sessions_campaign_started
    ON agent_sessions(campaign_id, started_at DESC);

CREATE INDEX IF NOT EXISTS idx_agent_sessions_status
    ON agent_sessions(status, ended_at DESC);

CREATE INDEX IF NOT EXISTS idx_agent_session_events_session
    ON agent_session_events(session_id, created_at ASC, id ASC);

INSERT OR IGNORE INTO schema_migrations(version, applied_at)
VALUES ('005_agent_sessions', CURRENT_TIMESTAMP);
