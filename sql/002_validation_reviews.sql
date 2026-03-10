PRAGMA foreign_keys=ON;

ALTER TABLE experiments ADD COLUMN eval_split TEXT NOT NULL DEFAULT 'search_val';
ALTER TABLE experiments ADD COLUMN run_purpose TEXT NOT NULL DEFAULT 'search';
ALTER TABLE experiments ADD COLUMN replay_source_experiment_id TEXT;
ALTER TABLE experiments ADD COLUMN validation_state TEXT NOT NULL DEFAULT 'not_required';
ALTER TABLE experiments ADD COLUMN validation_review_id TEXT;
ALTER TABLE experiments ADD COLUMN idea_signature TEXT;

CREATE TABLE IF NOT EXISTS validation_reviews (
    review_id TEXT PRIMARY KEY,
    source_experiment_id TEXT NOT NULL,
    campaign_id TEXT NOT NULL,
    review_type TEXT NOT NULL,
    eval_split TEXT NOT NULL,
    candidate_experiment_ids_json TEXT NOT NULL,
    comparator_experiment_ids_json TEXT NOT NULL DEFAULT '[]',
    seed_list_json TEXT NOT NULL DEFAULT '[]',
    candidate_metric_median REAL,
    comparator_metric_median REAL,
    delta_median REAL,
    decision TEXT NOT NULL,
    reason TEXT NOT NULL,
    review_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (source_experiment_id) REFERENCES experiments(experiment_id),
    FOREIGN KEY (campaign_id) REFERENCES campaigns(campaign_id)
);

CREATE INDEX IF NOT EXISTS idx_experiments_campaign_eval_purpose
    ON experiments(campaign_id, eval_split, run_purpose, started_at DESC);

CREATE INDEX IF NOT EXISTS idx_experiments_validation
    ON experiments(validation_state, validation_review_id);

CREATE INDEX IF NOT EXISTS idx_validation_reviews_campaign
    ON validation_reviews(campaign_id, review_type, created_at DESC);

INSERT OR IGNORE INTO schema_migrations(version, applied_at)
VALUES ('002_validation_reviews', CURRENT_TIMESTAMP);
