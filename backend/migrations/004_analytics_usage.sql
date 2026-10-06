-- TCA V0.5 Feature 9 — Analytics + AI usage

CREATE TABLE IF NOT EXISTS tca_ai_usage (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES tca_users(id) ON DELETE CASCADE,
    call_id TEXT REFERENCES tca_calls(id) ON DELETE SET NULL,
    operation TEXT NOT NULL,
    provider TEXT NOT NULL DEFAULT 'gemini',
    model TEXT NOT NULL,
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    total_tokens INTEGER NOT NULL DEFAULT 0,
    cached_tokens INTEGER NOT NULL DEFAULT 0,
    thoughts_tokens INTEGER NOT NULL DEFAULT 0,
    estimated_cost_usd DOUBLE PRECISION,
    status TEXT NOT NULL DEFAULT 'success',
    latency_ms INTEGER,
    occurred_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_tca_ai_usage_user_time
    ON tca_ai_usage(user_id, occurred_at DESC);

CREATE INDEX IF NOT EXISTS idx_tca_ai_usage_operation_time
    ON tca_ai_usage(operation, occurred_at DESC);

CREATE INDEX IF NOT EXISTS idx_tca_ai_usage_call
    ON tca_ai_usage(call_id);

INSERT INTO tca_cloud_schema_migrations (version)
VALUES ('004_analytics_usage')
ON CONFLICT (version) DO NOTHING;
