# TCA V0.5 — Deployment Checklist

## 1. Render backend

Create the web service from `render.yaml` or configure it manually.

Build:

```text
pip install -r requirements-production.txt
```

Start:

```text
uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT
```

Health:

```text
/health/ready
```

Required environment values:

- `TCA_ENV=production`
- `TCA_CLOUD_ENABLED=true`
- `TCA_CLOUD_REQUIRED=true`
- `TCA_AUTH_SECRET` — random, 32+ chars
- `DATABASE_URL` — production PostgreSQL
- `TCA_FRONTEND_URLS` — exact Netlify origin(s), comma-separated
- `TCA_ALLOWED_HOSTS` — Render hostname(s)
- `GEMINI_API_KEY`
- `GEMINI_MODEL`
- `TCA_ANALYTICS_ADMIN_EMAILS`

Recommended:

- S3/R2 credentials
- Gemini pricing variables

## 2. PostgreSQL

Feature 10 automatically applies the numbered SQL migrations on backend startup.

If migrating existing local beta accounts, run once from a machine that can access the production database:

```powershell
python backend\cloud_migrate.py
```

That migration now includes password hashes/salts and capture handoff state.

## 3. Netlify frontend

Build command:

```text
npm run build
```

Publish directory:

```text
dist
```

Set:

```text
VITE_API_BASE_URL=https://YOUR-BACKEND.onrender.com
```

`netlify.toml` already contains the SPA fallback.

## 4. Verify production persistence

- Create account.
- Log out.
- Log back in.
- Restart/redeploy backend.
- Log back in again.
- Complete onboarding.
- Create a conversation.
- Verify conversation appears after backend restart.
- Submit feedback.
- Verify feedback after restart.
- Open Analytics.
- Verify events/AI usage after restart.
- Verify second account cannot access first account's calls.

## 5. Verify security

- Backend rejects missing/short production auth secret.
- Backend rejects missing production database.
- Backend rejects missing Gemini key.
- CORS only allows configured frontend origin.
- Admin analytics is restricted by configured admin email(s).
- Gemini API key is never sent to the frontend bundle.

## 6. Production capture gate

Hosted capture uses the browser transport:

- microphone: `getUserMedia()`
- system/tab audio: `getDisplayMedia()` with audio sharing enabled
- upload: authenticated multipart `POST /calls/{call_id}/capture`
- backend storage: `mic_raw.webm` + `system_raw.webm`
- processing: existing Gemini transcription + notes pipeline

Render never needs direct access to a user's Windows audio devices. The browser sends the captured audio to Render over HTTPS.

For a private-beta capture test, use a current desktop Chrome/Edge browser and share a tab/window/screen with **audio enabled**.

The Windows floating companion remains a native launcher for the web capture flow; it is not required for hosted browser capture.
