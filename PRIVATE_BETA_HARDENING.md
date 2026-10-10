# Private-beta hardening and release checklist

## Included in this update
- Mobile browser capture automatically records microphone audio only; desktop capture still requests microphone plus shared system/tab audio when supported.
- Backend processing accepts a microphone-only capture and labels it as one-sided audio rather than requiring a fake/duplicated system track.
- Frontend API errors hide stack traces, provider names, raw 5xx details, and Gemini file-state diagnostics from end users while keeping actionable retry guidance.
- Signup UI includes show/hide password controls, confirmation, a basic strength meter, and stronger passphrase guidance.
- Mobile header/navigation wraps instead of clipping sign-out and the version badge.
- Loading screen, favicon, manifest and service-worker cache name are refreshed.
- Electron production defaults point at the hosted frontend/backend; local development URLs remain available when unpackaged and environment-overridden.

## Still required before public launch
1. **Email verification is not implemented in this patch.** Configure an email provider and add server-side verification tokens/expiry/rate limiting before allowing broad public signup. Password UX is not a substitute for verified email.
2. Build and test signed Windows installer/portable builds on a Windows build machine. The repository has Electron packaging configuration; this ZIP does not contain a verified installer binary.
3. Complete manual E2E: mobile microphone capture on real devices, desktop dual-track capture, processing retry, account isolation in both directions, feedback, analytics admin gating, and deletion/object cleanup.
4. Confirm all production secrets are set only in Render/Cloudflare secret managers, not in the ZIP or Git.
5. Confirm legal consent wording and retention/deletion policy for recordings in each beta jurisdiction.

## Local web test
From `frontend/`: `npm ci`, `npm run build`, `npm run lint`.
From repository root: `python -m compileall -q backend transcription intelligence`; run each smoke script under `tests/`.

## Electron development and packaging
From `TCA_V0.4_Windows_LoomStyle_Capture/`: `npm ci`, `npm start` for local development. For a production package, set `TCA_URL=https://clipian.netlify.app/` and `TCA_API_URL=https://clipian-api.onrender.com`, then run `npm run dist`. Build and smoke-test the installer on Windows before distributing it.

## Important microphone-only behavior
Mobile capture records sound heard by the phone microphone. It cannot capture isolated remote-call/system audio from another app. Use desktop tab/system capture or the Electron companion when separate system audio is needed.
