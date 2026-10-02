# TCA V0.5 — Cloud Foundation

This package adds the production cloud plumbing without moving the working
V0.4/V0.5 recording and local-memory pipeline yet.

## What this feature does

- Adds provider-neutral managed PostgreSQL configuration through `DATABASE_URL`.
- Adds S3-compatible object storage configuration for AWS S3, Cloudflare R2,
  or another S3-compatible provider.
- Adds an idempotent PostgreSQL foundation migration.
- Adds a cloud health endpoint: `GET /health/cloud`.
- Adds startup cloud initialization when `TCA_CLOUD_ENABLED=true`.
- Adds a safe `TCA_CLOUD_REQUIRED` switch for production fail-fast behavior.
- Mirrors authenticated users into the cloud foundation `tca_users` table
  when cloud mode is enabled.
- Adds a migration/sync command:
  `python -m backend.cloud_migrate`.
- Adds an object-key convention for future cloud conversation artifacts.
- Keeps local auth and local conversation storage authoritative for now.
  Cloud Memory is the next feature and will switch persisted conversation
  data to the cloud layer.

## Local development

Leave:

```env
TCA_CLOUD_ENABLED=false
TCA_CLOUD_REQUIRED=false
```

The existing TCA app behaves as before.

Run:

```powershell
python tests/cloud_foundation_smoke.py
```

## Cloud configuration

Set:

```env
TCA_CLOUD_ENABLED=true
TCA_CLOUD_REQUIRED=true

DATABASE_URL=postgresql://...

S3_ENDPOINT_URL=
S3_BUCKET=
S3_ACCESS_KEY_ID=
S3_SECRET_ACCESS_KEY=
S3_REGION=auto
S3_OBJECT_PREFIX=tca
```

For AWS S3, `S3_ENDPOINT_URL` can be left empty.

For Cloudflare R2, set the R2 S3 endpoint and credentials.

## Initialize the cloud foundation

After the database is reachable:

```powershell
python -m backend.cloud_migrate
```

This creates the foundation tables and mirrors the existing local-auth users.

## Health

Local:

```text
GET /health
```

Cloud:

```text
GET /health/cloud
```

With cloud disabled, `/health/cloud` returns:

```json
{
  "status": "disabled",
  "enabled": false
}
```

With PostgreSQL and object storage configured and reachable, it reports
`status: ok`.

## Important boundary

This feature intentionally does NOT upload recordings/transcripts or replace
the local call repository yet. That belongs to **Cloud Memory**, the next
feature. Keeping that boundary makes the change reversible and protects the
already-tested recorder and processing pipeline.
