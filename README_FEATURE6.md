# TCA V0.5 — Feature 6: Frontend Auth + Onboarding

This implementation builds on the existing V0.5 authentication, user identity, conversation ownership, and cloud-memory work.

## What changed

- Authentication is now handled by an in-app `AuthGate` state transition instead of a full-page reload after login/signup.
- The authenticated user returned by `/auth/login` or `/auth/signup` is immediately used by the frontend.
- Incomplete accounts go directly to onboarding; completed accounts go directly to TCA.
- The existing `?capture=1` launch URL is preserved through login/onboarding because navigation no longer reloads the page.
- Onboarding shows the signed-in email, confirms the name TCA will use for local-speaker memory, and offers an explicit "Use a different account" action.
- Top-bar sign-out now returns to the authentication screen through the existing auth-expired event instead of reloading the browser.
- Existing backend auth, ownership, cloud memory, and recorder behavior are unchanged.

## Complete files in this implementation package

- `frontend/src/main.tsx`
- `frontend/src/components/AuthScreen.tsx`
- `frontend/src/components/OnboardingScreen.tsx`
- `frontend/src/components/TopBar.tsx`
- `frontend/src/styles.css`

## Validation

- Frontend TypeScript project compilation (`tsc -b`) passed as part of `npm run build`.
- The Vite build step could not execute in the Linux validation container because the uploaded `node_modules` contains Windows-native package permissions/binaries; run `npm install` / `npm run build` locally on Windows.
- Existing backend smoke tests passed:
  - Feature 3 identity smoke test
  - Feature 2 ownership smoke test
  - Cloud Foundation smoke test
  - Cloud Memory smoke test
