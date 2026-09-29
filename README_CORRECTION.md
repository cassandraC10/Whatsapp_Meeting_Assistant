# TCA V0.5 Feature 3 Correction — Companion Account Switch

The browser session and the Windows Loom-style companion intentionally keep separate
authentication tokens. That means logging the browser into Cassie does not silently
replace a previously stored companion session (for example User B).

This correction adds an explicit **Switch account** action to the companion's consent
panel. It clears the companion's encrypted token and immediately returns to companion
login.

This keeps account ownership explicit and prevents one desktop capture session from
silently changing identity underneath the user.

## E2E

1. Open TCA in the browser and sign in as Cassie.
2. Open the Windows Capture bubble.
3. If it says another user, click **Switch account**.
4. Sign in as Cassie in the bubble.
5. The consent panel must say **Signed in as Cassie**.
6. Start a short capture and confirm it appears in Cassie's calls.
7. Sign out of the companion from the tray menu and repeat with another account.

The browser and companion are separate sessions by design for now. A later production
pass can add a proper cross-device/session-management mechanism.
