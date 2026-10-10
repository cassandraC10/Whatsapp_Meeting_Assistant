# Local test → push → deploy (v5)

## Before extracting
- Make a backup or a fresh branch of your current repository.
- Extract this ZIP into the existing repository root and allow source files to be overwritten.
- This ZIP intentionally does not include `.git`, `.env`, `.env.production`, runtime recordings, local databases, `node_modules`, or stale `frontend/dist` output. Your existing Git repository and local secrets remain untouched.

## 1. Install and build the frontend (PowerShell)

```powershell
cd frontend
npm ci
npm run build
npm run lint
cd ..
```

## 2. Run backend checks

```powershell
python -m compileall -q backend transcription intelligence
$env:PYTHONPATH = (Get-Location).Path
Get-ChildItem tests\\*_smoke.py | Sort-Object Name | ForEach-Object {
    python $_.FullName
    if ($LASTEXITCODE -ne 0) {
        throw "Smoke test failed: $($_.Name)"
    }
}
```

The smoke tests use temporary/local test data; they do not validate your production Render/R2/Gemini credentials. Run with a test environment, not a production `.env` copied into a test environment.

## 3. Manual local E2E

1. Start the backend using your existing local development command and test environment.
2. Start the frontend with `cd frontend; npm run dev`.
3. Sign up with a new test account and verify the password confirmation/strength feedback.
4. Desktop Chrome/Edge: capture a short consensual test meeting with tab/system audio enabled; process it; refresh; reopen it.
5. Mobile browser: capture a short consensual test meeting. Mobile uses microphone-only capture; it cannot isolate audio playing in another app.
6. Create a second test account and verify neither account can see, fetch, edit, or delete the other's calls.
7. Test processing retry and confirm technical provider/stack details are not shown in user-facing errors.

## 4. Electron package

From `TCA_V0.4_Windows_LoomStyle_Capture` on a Windows build machine:

```powershell
npm ci
$env:TCA_URL = "https://clipian.netlify.app/"
$env:TCA_API_URL = "https://clipian-api.onrender.com"
npm run dist
```

Test the resulting installer and portable build on a clean Windows profile before distributing. This ZIP contains Electron source/configuration, not a signed, validated installer binary.

## 5. Review and commit

```powershell
git status
```

Review the changes. Stage only the files from this update (frontend auth/capture/API/styles/manifest/favicon/service worker, backend capture/processing, transcription, Electron source/package/icon, tests and the two release docs). Never stage `.env` or production secrets.

```powershell
git add frontend/src frontend/index.html frontend/public/favicon.svg frontend/public/icons/icon-192.png frontend/public/icons/icon-512.png frontend/public/manifest.webmanifest frontend/public/sw.js backend/app/main.py backend/app/processing_service.py backend/app/auth.py transcription/transcriber.py tests PRIVATE_BETA_HARDENING.md LOCAL_TEST_AND_DEPLOY.md TCA_V0.4_Windows_LoomStyle_Capture/src/main.js TCA_V0.4_Windows_LoomStyle_Capture/src/icon-512.png TCA_V0.4_Windows_LoomStyle_Capture/package.json
git commit -m "Harden private beta capture and responsive UX"
git push origin v5
```

Netlify should rebuild from `v5`; Render should redeploy the backend from `v5`. Wait for both deployments to be healthy before repeating production E2E.

## Release gates still open

- Email OTP/verification is **not implemented in this patch**. Add a provider-backed verification flow (single-use token/code, expiry, rate limiting, verified status enforced by backend) before public launch. A frontend-only verification screen is not security.
- Browser/Electron production installers need real-device/Windows testing.
- Complete two-account isolation, mobile capture, feedback/analytics permissions, retention/deletion, and retry tests before announcing public availability.
