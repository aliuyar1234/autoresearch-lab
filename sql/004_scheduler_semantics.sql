PRAGMA foreign_keys=ON;

ALTER TABLE proposals ADD COLUMN idea_signature TEXT;
ALTER TABLE proposals ADD COLUMN mutation_paths_json TEXT NOT NULL DEFAULT '[]';

CREATE INDEX IF NOT EXISTS idx_proposals_campaign_idea_signature
    ON proposals(campaign_id, idea_signature, lane);

CREATE INDEX IF NOT EXISTS idx_experiments_campaign_idea_signature
    ON experiments(campaign_id, idea_signature, lane);

INSERT OR IGNORE INTO schema_migrations(version, applied_at)
VALUES ('004_scheduler_semantics', CURRENT_TIMESTAMP);
