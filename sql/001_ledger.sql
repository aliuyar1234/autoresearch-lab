-- 001_ledger.sql
-- Initial SQLite schema for Autoresearch Lab

PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS campaigns (
    campaign_id TEXT PRIMARY KEY,
    version TEXT NOT NULL,
    title TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    comparability_group TEXT NOT NULL,
    primary_metric_name TEXT NOT NULL,
    manifest_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS proposals (
    proposal_id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL,
    family TEXT NOT NULL,
    kind TEXT NOT NULL,
    lane TEXT NOT NULL,
    status TEXT NOT NULL,
    generator TEXT NOT NULL,
    parent_ids_json TEXT NOT NULL DEFAULT '[]',
    complexity_cost INTEGER NOT NULL DEFAULT 0,
    hypothesis TEXT NOT NULL,
    rationale TEXT NOT NULL,
    config_overrides_json TEXT NOT NULL DEFAULT '{}',
    proposal_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (campaign_id) REFERENCES campaigns(campaign_id)
);

CREATE TABLE IF NOT EXISTS experiments (
    experiment_id TEXT PRIMARY KEY,
    proposal_id TEXT,
    campaign_id TEXT NOT NULL,
    lane TEXT NOT NULL,
    status TEXT NOT NULL,
    disposition TEXT,
    crash_class TEXT,
    seed INTEGER,
    git_commit TEXT,
    device_profile TEXT,
    backend TEXT,
    proposal_family TEXT,
    proposal_kind TEXT,
    complexity_cost INTEGER,
    budget_seconds INTEGER NOT NULL,
    primary_metric_name TEXT,
    primary_metric_value REAL,
    metric_delta REAL,
    tokens_per_second REAL,
    peak_vram_gb REAL,
    summary_path TEXT,
    artifact_root TEXT NOT NULL,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (proposal_id) REFERENCES proposals(proposal_id),
    FOREIGN KEY (campaign_id) REFERENCES campaigns(campaign_id)
);

CREATE TABLE IF NOT EXISTS artifacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    experiment_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    relative_path TEXT NOT NULL,
    sha256 TEXT,
    size_bytes INTEGER,
    retention_class TEXT NOT NULL,
    content_type TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (experiment_id) REFERENCES experiments(experiment_id)
);

CREATE TABLE IF NOT EXISTS champions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id TEXT NOT NULL,
    experiment_id TEXT NOT NULL,
    reason TEXT NOT NULL,
    rank_bucket TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (campaign_id) REFERENCES campaigns(campaign_id),
    FOREIGN KEY (experiment_id) REFERENCES experiments(experiment_id)
);

CREATE TABLE IF NOT EXISTS daily_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id TEXT NOT NULL,
    report_date TEXT NOT NULL,
    report_path TEXT NOT NULL,
    report_json_path TEXT,
    run_count INTEGER NOT NULL DEFAULT 0,
    promoted_count INTEGER NOT NULL DEFAULT 0,
    failed_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    FOREIGN KEY (campaign_id) REFERENCES campaigns(campaign_id)
);

CREATE INDEX IF NOT EXISTS idx_proposals_campaign_status
    ON proposals(campaign_id, status, lane);

CREATE INDEX IF NOT EXISTS idx_proposals_family
    ON proposals(campaign_id, family, kind, lane);

CREATE INDEX IF NOT EXISTS idx_experiments_campaign_started
    ON experiments(campaign_id, started_at DESC);

CREATE INDEX IF NOT EXISTS idx_experiments_proposal
    ON experiments(proposal_id);

CREATE INDEX IF NOT EXISTS idx_experiments_status
    ON experiments(status, disposition);

CREATE INDEX IF NOT EXISTS idx_artifacts_experiment
    ON artifacts(experiment_id, kind);

CREATE INDEX IF NOT EXISTS idx_champions_campaign
    ON champions(campaign_id, created_at DESC);

CREATE UNIQUE INDEX IF NOT EXISTS idx_daily_reports_campaign_date
    ON daily_reports(campaign_id, report_date);

INSERT OR IGNORE INTO schema_migrations(version, applied_at)
VALUES ('001_ledger', CURRENT_TIMESTAMP);
