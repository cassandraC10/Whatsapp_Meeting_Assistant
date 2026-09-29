# TCA V0.5 Feature 2 — Private Conversation Ownership

This feature makes saved conversations private to the authenticated TCA user.

## Backend

Every conversation now carries `user_id`. Authenticated API routes scope calls, search, Ask TCA, People, tasks, transcripts, notes, follow-ups, recording state and deletion to the current user.

Existing V0.4 local calls without an owner are claimed once by the first authenticated account that signs in. New calls are always created with an owner.

## Windows companion

The native floating Capture companion now signs in directly inside the native panel and stores the access token using Electron `safeStorage` when available. The token is sent with capture requests so the bubble continues to work after the API becomes authenticated.

The tray still uses the blue TCA icon.

## Test order

1. Start backend.
2. Start frontend.
3. Start the Windows companion.
4. Create/login as User A in the web app.
5. Confirm User A sees their calls.
6. Create a new call as User A.
7. Sign out.
8. Create/login as User B.
9. Confirm User B does not see User A's calls.
10. Attempt the User A call URL directly while logged in as User B; it must return 404.
11. Search, Ask TCA, People and tasks as User B; none may surface User A data.
12. Log back into User A and confirm the call is visible again.
13. Start the native companion, sign in once, then create a capture.
14. Confirm the captured call appears only in the signed-in user's account.

## Important

`TCA_AUTH_SECRET` must be set to a strong random secret in production. The development fallback in `auth.py` is for local testing only.
