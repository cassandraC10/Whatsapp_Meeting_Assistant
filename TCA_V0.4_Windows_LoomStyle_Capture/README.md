# TCA V0.4 — Loom-style Windows Floating Capture

This version keeps the native floating bubble on Windows and moves the capture
flow into the bubble itself.

Flow:

Bubble -> consent/title -> Start recording -> Pause/Resume -> Finish ->
processing -> open TCA

The browser is NOT opened when the user starts a recording.

The companion talks directly to the local FastAPI backend at
http://127.0.0.1:8000, while the existing TCA web app remains responsible for
the full memory/history experience.

The supplied icon-512.png is used as the Windows tray/app icon.

## Apply

Replace the files in your existing `TCA_V0.4_FloatingCapture_Windows` folder
with the files in this package. A new `src/bubble.js` file is included.

Do NOT replace the frontend package.json.

Then from TCA_V0.4_FloatingCapture_Windows:

npm start

You do not need to reinstall Electron if v44.3.0 is already installed.

## Test

1. Keep the backend running on 127.0.0.1:8000.
2. Keep the frontend running on localhost:5173 if you want TCA available
   after processing.
3. Start the companion.
4. Click the floating blue bubble.
5. Enter an optional title.
6. Confirm that everyone knows they are being recorded.
7. Click Start recording.
8. Pause/resume and finish.
9. The companion processes the saved call.
10. TCA opens after processing completes.

If the backend is not running, the native capture panel will show the error
instead of silently doing nothing.
