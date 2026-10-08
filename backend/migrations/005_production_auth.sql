-- TCA V0.5 Feature 10 — production-persistent authentication
-- Password material remains server-side only and is never returned to clients.

ALTER TABLE tca_users
    ADD COLUMN IF NOT EXISTS password_hash TEXT;

ALTER TABLE tca_users
    ADD COLUMN IF NOT EXISTS password_salt TEXT;

CREATE TABLE IF NOT EXISTS tca_capture_handoffs (
    code_hash TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES tca_users(id) ON DELETE CASCADE,
    created_at BIGINT NOT NULL,
    expires_at BIGINT NOT NULL,
    used_at BIGINT
);

CREATE INDEX IF NOT EXISTS idx_tca_capture_handoffs_user
    ON tca_capture_handoffs(user_id);

CREATE INDEX IF NOT EXISTS idx_tca_capture_handoffs_expiry
    ON tca_capture_handoffs(expires_at);

INSERT INTO tca_cloud_schema_migrations (version)
VALUES ('005_production_auth')
ON CONFLICT (version) DO NOTHING;
