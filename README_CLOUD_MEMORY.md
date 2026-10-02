# TCA V0.5 — Cloud Memory

Feature 5 moves durable conversation memory from the server's local filesystem
into managed PostgreSQL, with S3-compatible object storage for recordings and
conversation artifacts.

## What is persisted in PostgreSQL

Each owned conversation stores:

- call identity and ownership
- title, created time, duration and status
- failure state
- structured conversation notes
- stateful tasks
- combined transcript text
- structured transcript JSON

## What is stored in object storage

When configured, TCA stores the conversation artifacts under an account-owned
prefix:

```text
<tca-prefix>/users/<user-id>/calls/<call-id>/...
```

Typical objects include:

- metadata.json
- notes.json
- tasks.json
- combined_transcript.txt
- transcript.json
- my_transcript.txt
- their_transcript.txt
- meeting.wav
- mic_raw.wav
- system_raw.wav

The PostgreSQL `tca_call_objects` table records the object key, content type,
size and SHA-256 hash.

## Local development

Keep cloud disabled:

```env
TCA_CLOUD_ENABLED=false
TCA_CLOUD_REQUIRED=false
```

Run:

```powershell
python tests/cloud_foundation_smoke.py
python tests/cloud_memory_smoke.py
```

The existing local recorder and memory flow continues to work unchanged.

## Production configuration

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

With `TCA_CLOUD_REQUIRED=true`, the backend fails fast if PostgreSQL or object
storage cannot be initialized. This prevents a production deployment from
silently falling back to ephemeral local storage.

## Migration

The startup migration runner applies all SQL files in
`backend/migrations/` in filename order. You can also run:

```powershell
python -m backend.cloud_migrate
```

This applies both the cloud foundation and cloud memory schema and mirrors the
existing local-auth users into `tca_users`.

## Important behavior

- New calls remain owned by the authenticated user.
- Cloud mode becomes the source for completed call metadata and memory.
- Local files remain the active recording/processing workspace.
- When a completed cloud call is requested after a restart, its durable
  memory is hydrated back into the local workspace as a cache.
- The recorder does not depend on PostgreSQL or S3 while cloud mode is off.
- Cloud failures are fail-fast only when `TCA_CLOUD_REQUIRED=true`.
