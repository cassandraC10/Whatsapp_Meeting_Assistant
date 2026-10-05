# TCA V0.5 Feature 7 — Electron authenticated capture

## Implementation

This package connects the signed-in TCA web session to the Windows floating
Capture companion using a short-lived, single-use handoff code.

The browser never places the bearer access token in the custom protocol URL.
Electron exchanges the opaque handoff code with the backend and stores the
returned access token using Electron `safeStorage` where available.

Included complete replacement files:

- `backend/app/auth.py`
- `backend/app/main.py`
- `backend/app/models.py`
- `frontend/src/api.ts`
- `frontend/src/components/TopBar.tsx`
- `frontend/src/styles.css`
- `TCA_V0.4_Windows_LoomStyle_Capture/src/main.js`
- `TCA_V0.4_Windows_LoomStyle_Capture/src/preload.js`
- `TCA_V0.4_Windows_LoomStyle_Capture/src/bubble.js`
- `TCA_V0.4_Windows_LoomStyle_Capture/src/bubble.html`
- `TCA_V0.4_Windows_LoomStyle_Capture/package.json`
- `TCA_V0.4_Windows_LoomStyle_Capture/package-lock.json`
- `tests/capture_auth_smoke.py`

## Apply

Replace the corresponding files in the current V0.5 project. Do not replace
the frontend package with the Electron package.

Then run the backend and frontend normally. From the Electron folder run:

```powershell
npm install
npm start
```

If Electron's Windows binary has previously been partially downloaded, verify:

```powershell
Test-Path .\node_modules\electron\dist\electron.exe
```

It should be `True`.

## E2E

1. Sign into TCA in the browser.
2. Confirm onboarding is complete.
3. Click **Capture** in the TCA top bar.
4. The Windows companion should open and show the same account name.
5. Click the floating bubble.
6. Confirm **Signed in as <your name>**.
7. Start a real short conversation recording.
8. Finish it.
9. Verify the call is saved under the same account in TCA.
10. Use **Switch account** in the companion and verify the next capture uses the newly connected account.

Fallback: the companion still supports direct email/password sign-in.
