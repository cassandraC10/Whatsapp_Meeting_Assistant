-- TCA V0.5 Cloud Memory
-- Durable conversation memory and object references.

CREATE TABLE IF NOT EXISTS tca_calls (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES tca_users(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    duration_seconds DOUBLE PRECISION NOT NULL DEFAULT 0,
    status TEXT NOT NULL,
    failure_reason TEXT,
    notes_json JSONB,
    tasks_json JSONB,
    transcript_text TEXT,
    transcript_json JSONB,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tca_calls_user_created
    ON tca_calls(user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_tca_calls_user_status
    ON tca_calls(user_id, status);

CREATE TABLE IF NOT EXISTS tca_call_objects (
    id BIGSERIAL PRIMARY KEY,
    call_id TEXT NOT NULL REFERENCES tca_calls(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL REFERENCES tca_users(id) ON DELETE CASCADE,
    relative_path TEXT NOT NULL,
    object_key TEXT NOT NULL UNIQUE,
    content_type TEXT,
    size_bytes BIGINT,
    sha256 TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(call_id, relative_path)
);

CREATE INDEX IF NOT EXISTS idx_tca_call_objects_call_id
    ON tca_call_objects(call_id);

CREATE INDEX IF NOT EXISTS idx_tca_call_objects_user_id
    ON tca_call_objects(user_id);

INSERT INTO tca_cloud_schema_migrations (version)
VALUES ('002_cloud_memory')
ON CONFLICT (version) DO NOTHING;
