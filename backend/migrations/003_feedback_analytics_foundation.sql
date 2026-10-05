-- TCA V0.5 Feature 8 — Feedback + Analytics event foundation
-- Feedback stores the current user choice for each conversation.
-- Product events are append-only and are the shared foundation for Feature 9 Analytics.

CREATE TABLE IF NOT EXISTS tca_feedback (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES tca_users(id) ON DELETE CASCADE,
    call_id TEXT NOT NULL REFERENCES tca_calls(id) ON DELETE CASCADE,
    rating TEXT NOT NULL CHECK (rating IN ('helpful', 'needs_work')),
    comment TEXT,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    UNIQUE(user_id, call_id)
);

CREATE INDEX IF NOT EXISTS idx_tca_feedback_user_updated
    ON tca_feedback(user_id, updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_tca_feedback_call
    ON tca_feedback(call_id);

CREATE TABLE IF NOT EXISTS tca_product_events (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES tca_users(id) ON DELETE CASCADE,
    event_name TEXT NOT NULL,
    call_id TEXT REFERENCES tca_calls(id) ON DELETE SET NULL,
    occurred_at TIMESTAMPTZ NOT NULL,
    properties_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    source TEXT NOT NULL DEFAULT 'backend'
);

CREATE INDEX IF NOT EXISTS idx_tca_product_events_user_time
    ON tca_product_events(user_id, occurred_at DESC);

CREATE INDEX IF NOT EXISTS idx_tca_product_events_name_time
    ON tca_product_events(event_name, occurred_at DESC);

CREATE INDEX IF NOT EXISTS idx_tca_product_events_call
    ON tca_product_events(call_id);

INSERT INTO tca_cloud_schema_migrations (version)
VALUES ('003_feedback_analytics_foundation')
ON CONFLICT (version) DO NOTHING;
