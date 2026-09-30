-- TCA V0.5 Cloud Foundation
-- Foundation-only schema. Conversation payloads remain local until
-- Cloud Memory is enabled in the next feature.

CREATE TABLE IF NOT EXISTS tca_cloud_schema_migrations (
    version TEXT PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS tca_users (
    id TEXT PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    onboarding_completed BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS tca_objects (
    id BIGSERIAL PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES tca_users(id) ON DELETE CASCADE,
    object_key TEXT NOT NULL UNIQUE,
    content_type TEXT,
    size_bytes BIGINT,
    sha256 TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tca_objects_user_id
    ON tca_objects(user_id);

INSERT INTO tca_cloud_schema_migrations (version)
VALUES ('001_cloud_foundation')
ON CONFLICT (version) DO NOTHING;
