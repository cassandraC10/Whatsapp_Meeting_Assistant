# TCA V0.4 Windows Floating Capture — Click + Blue Tray Fix

Replace the corresponding files in your existing
`TCA_V0.4_FloatingCapture_Windows/src/` folder:

- `bubble.html`
- `bubble.js` (new)
- `main.js`
- `preload.js`
- `tray.png`

The click bug was caused by `bubble.html` using an inline script while its
Content-Security-Policy only allows `script-src 'self'`. The click handler is
now in `bubble.js`, which is allowed by that CSP.

The tray icon has also been recolored using the blue from the supplied
Conversation Assistant icon.

No package reinstall is required.

After replacing the files:
1. Stop the floating companion with Ctrl+C.
2. Run `npm start` from `TCA_V0.4_FloatingCapture_Windows`.
3. Click the floating bubble.
4. TCA should open at `http://localhost:5173/?capture=1`.
