# TCA V0.5 — Feature 3: Onboarding + User Identity

This package is built on the V0.5 Feature 2 private-ownership implementation.

## What changed

### Account identity
- Auth users now have `onboarding_completed`.
- Existing V0.5 accounts are migrated to onboarding-required automatically.
- New accounts start with onboarding incomplete.
- `PATCH /auth/me` saves the user's display name and completes onboarding.

### Conversation identity
- The authenticated account name is passed into the processing pipeline as `local_speaker_name`.
- Generated participant memory identifies the local speaker from the account profile with source `account-profile`.
- The model is instructed to use first-person language (`I`, `my`) when referring to the local speaker rather than `the local speaker`, `the TCA user`, or `ME`.
- Remote participant identity rules remain unchanged: explicit call-title identity remains authoritative and unknown names remain unknown.
- Local action items receive the authenticated user's name as `owner_name`.

### Web onboarding
- First authenticated launch shows a short identity confirmation screen.
- The user can confirm/edit the name TCA should use for their memory.
- The existing app opens after onboarding is complete.
- The top bar shows the authenticated user's name.

### Windows capture companion
- When the blue bubble is opened with a stored token, the companion refreshes `/auth/me` and shows `Signed in as <name>` in the consent panel.
- Recording ownership remains enforced by the authenticated backend session.

## Files to replace/add

Replace the corresponding complete files in the V0.5 project:

- `backend/app/auth.py`
- `backend/app/models.py`
- `backend/app/main.py`
- `backend/app/processing_service.py`
- `intelligence/summarizer.py`
- `frontend/src/api.ts`
- `frontend/src/main.tsx`
- `frontend/src/styles.css`
- `frontend/src/components/TopBar.tsx`

Add:

- `frontend/src/components/OnboardingScreen.tsx`
- `tests/feature3_identity_smoke.py`

For the Windows companion, replace:

- `TCA_V0.4_Windows_LoomStyle_Capture/src/main.js`
- `TCA_V0.4_Windows_LoomStyle_Capture/src/bubble.js`
- `TCA_V0.4_Windows_LoomStyle_Capture/src/bubble.html`

## Local test

Backend:

```powershell
# restart FastAPI after replacing backend files
```

Frontend:

```powershell
cd frontend
npm run build
npm run dev
```

Windows companion:

```powershell
cd TCA_V0.4_Windows_LoomStyle_Capture
npm start
```

Smoke test:

```powershell
python tests/feature3_identity_smoke.py
```

## Expected E2E

1. Log in with an existing Feature 2 account.
2. Complete the identity screen and confirm the name.
3. Open TCA and confirm the name appears in the top bar.
4. Start a new call and process it.
5. In the saved notes, `participants` should contain:
   - `role: me`
   - the account name
   - `source: account-profile`
6. The remote participant should still use the explicit call-title name when present.
7. The Windows bubble consent panel should show `Signed in as <name>`.
8. Sign in as another account and verify its identity is independent.

Gemini-dependent note: the final natural-language `I`/`my` wording is enforced by the summarizer prompt and sanitized participant identity. The local static environment used to build this package does not contain the Gemini SDK, so the actual generated-note wording must be verified on the Windows development environment where TCA already runs Gemini successfully.
