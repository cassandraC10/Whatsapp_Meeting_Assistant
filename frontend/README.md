# TCA V0.4 — Windows Floating Capture

Native Windows companion for the local TCA web app.

## What it does

- Keeps a small Capture button above other Windows apps.
- Clicking it opens TCA directly at `/?capture=1`.
- TCA remains responsible for consent, recording, processing, memory, and the rest of the product.
- A system-tray menu provides Capture, Open TCA, reposition, and Quit.

## Run locally

Start TCA first:

```powershell
cd frontend
npm run dev
```

That gives:

`http://localhost:5173/`

Then, from this companion folder:

```powershell
npm install
npm start
```

The floating Capture button appears near the bottom-right of the primary display.

## Build the Windows app

```powershell
npm run dist
```

or:

```powershell
npm run dist:portable
```

Builds are placed in `dist/`.

## Preview server

To point the companion at Vite preview instead:

```powershell
$env:TCA_URL="http://localhost:4173/"
npm start
```

The companion adds `?capture=1` automatically.

## Later deployment

Set `TCA_URL` to the deployed TCA origin.

## Product boundary

This is intentionally a native launcher, not a second recorder. The one-tap surface is native because a normal browser/PWA cannot stay above arbitrary Windows applications. The click hands control to the existing TCA web capture flow, which remains consent-first.
