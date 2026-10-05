# TCA — Windows authenticated Capture companion

This companion provides the Windows Loom-style floating Capture button for the
V0.5 private beta.

## V0.5 Feature 7 — Electron authenticated capture

The companion can now be connected directly to the currently signed-in TCA
browser account without copying a bearer token into the URL.

Flow:

Browser TCA -> Capture button -> short-lived one-time handoff code ->
`tca-capture://` -> Electron -> backend exchange -> encrypted local token ->
authenticated Capture.

The handoff code is single-use and expires after two minutes. The resulting
access token is stored with Electron `safeStorage` when Windows encryption is
available.

The companion still supports direct email/password sign-in as a fallback.

If the account has not completed TCA identity onboarding, Capture will ask the
user to finish setup in the web app before recording can begin.

## Development

Keep the backend running on `127.0.0.1:8000` and the frontend on
`localhost:5173`.

From this folder:

```powershell
npm start
```

Electron 44.3.0 is pinned in `package.json`.

## Authenticated Capture E2E

1. Start the backend.
2. Start the frontend.
3. Start this Electron companion.
4. Sign into TCA in the browser.
5. Click **Capture** in the TCA top bar.
6. The floating companion should open as the same signed-in user.
7. Click the bubble and confirm the panel says **Signed in as <your name>**.
8. Give consent and record a short real conversation.
9. Pause/resume once if desired.
10. Finish the call.
11. The companion should process it and open TCA.
12. Verify the saved conversation belongs to the same account.

## Account switching

Use **Switch account** in the companion or **Sign out of Capture** from the
tray menu. This clears the locally stored companion token.

## Production packaging

The Electron builder configuration registers the `tca-capture://` protocol
for the packaged Windows application.

```powershell
npm run dist
```

or:

```powershell
npm run dist:portable
```
