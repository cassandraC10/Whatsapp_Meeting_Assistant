# TCA V0.5 — Feature 10: Production Configuration

Feature 10 prepares TCA for a hosted private beta without changing the product loop.

## Included

- Environment-aware backend configuration (`development`, `staging`, `production`)
- Production secret validation
- Environment-driven CORS and allowed hosts
- Security response headers and gzip compression
- `/health`, `/health/cloud`, and `/health/ready`
- PostgreSQL-backed authentication when cloud mode is enabled
- Durable cloud capture handoff codes
- Migration `005_production_auth.sql`
- Local-auth migration helper via `python backend/cloud_migrate.py`
- Production dependency file for Linux hosting
- Netlify configuration
- Render configuration
- Production frontend API configuration
- Configurable beta limits for future server-side enforcement
- Configurable Gemini cost metering

## Production architecture

```text
Netlify frontend
      |
      v
Render FastAPI
      |
      +--> PostgreSQL (auth + conversations + feedback + events + AI usage)
      |
      +--> Gemini API
      |
      +--> S3/R2 (optional but recommended for durable raw audio)
```

## Important capture limitation

The current recorder is a Windows/local audio-device recorder. A Linux Render instance cannot access the user's microphone or Windows system audio.

Therefore `TCA_CAPTURE_MODE=local_server` is suitable for the existing local Windows/Electron capture workflow, but it is **not a production hosted recording solution**.

Do not claim hosted capture is production-ready until the browser/native capture client uploads audio to the backend (or the recorder runs locally beside the user).

Feature 10 deliberately makes this limitation explicit instead of silently pretending Render can record a user's PC.

## Local development

Use the existing workflow. Keep `TCA_CLOUD_ENABLED=false` for local-only mode unless you are intentionally testing PostgreSQL.

## Hosted deployment

1. Create PostgreSQL.
2. Create S3/R2 storage if raw audio should survive restarts.
3. Deploy Render using `render.yaml`.
4. Set all `sync: false` secrets/URLs in Render.
5. Run `python backend/cloud_migrate.py` once if migrating existing local beta accounts.
6. Deploy Netlify with `VITE_API_BASE_URL=https://<render-service>.onrender.com`.
7. Verify `/health/ready` returns `ready`.
8. Verify signup/login and account persistence.
9. Verify cloud conversation ownership and analytics persistence.
10. Keep hosted recording disabled until browser/native upload capture is deployed.

## Production environment

Copy `.env.production.example` into your deployment configuration. Never commit a real `.env` or provider API key.

## Private beta gate

Deployment is not the same as private-beta readiness. The final beta gate must include:

- account creation/login after a backend restart
- onboarding persistence
- cross-account conversation isolation
- feedback persistence
- analytics persistence
- Gemini processing
- capture from the user's device
- deletion/ownership checks
- production CORS
- production health/readiness

The current Feature 10 package completes the production configuration and persistence foundation. Hosted capture remains the explicit final architecture item before a fully hosted capture E2E.
