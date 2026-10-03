import { useState } from "react";

import type { AuthUser } from "../api";
import {
  clearAuthToken,
  updateCurrentUserProfile,
} from "../api";

type OnboardingScreenProps = {
  user: AuthUser;
  onComplete: (user: AuthUser) => void;
  onSignOut: () => void;
};

export function OnboardingScreen({
  user,
  onComplete,
  onSignOut,
}: OnboardingScreenProps) {
  const [name, setName] = useState(user.name);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (busy) {
      return;
    }

    setBusy(true);
    setError("");

    try {
      const updated = await updateCurrentUserProfile(name, true);
      onComplete(updated);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Could not save your identity.",
      );
    } finally {
      setBusy(false);
    }
  }

  function signOut() {
    if (busy) {
      return;
    }

    clearAuthToken();
    onSignOut();
  }

  const previewName = name.trim() || "You";

  return (
    <main className="onboarding-screen">
      <section className="onboarding-card" aria-labelledby="onboarding-title">
        <div className="auth-brand">
          <span className="auth-brand-mark">TCA</span>
          <span>The Call Assistant</span>
        </div>

        <div className="onboarding-account">
          <span>Signed in as</span>
          <strong>{user.email}</strong>
        </div>

        <div className="onboarding-copy">
          <span className="section-label">One quick thing</span>
          <h1 id="onboarding-title">Make your memory yours.</h1>
          <p>
            This is the name TCA will use for <strong>you</strong> when it turns
            a conversation into memory.
          </p>
        </div>

        <form className="onboarding-form" onSubmit={submit}>
          <label>
            <span>Your name</span>
            <input
              value={name}
              onChange={(event) => setName(event.target.value)}
              autoComplete="name"
              autoFocus
              minLength={2}
              maxLength={120}
              required
            />
          </label>

          <div className="onboarding-identity-card">
            <span className="onboarding-identity-dot" aria-hidden="true" />
            <div>
              <strong>{previewName}</strong>
              <p>
                TCA will recognise this as the local speaker in your saved
                conversations and use <strong>I</strong> / <strong>my</strong>
                when referring to you in memory.
              </p>
            </div>
          </div>

          {error && (
            <div className="auth-error" role="alert">
              {error}
            </div>
          )}

          <button className="auth-submit" type="submit" disabled={busy}>
            {busy ? "Saving…" : "Continue to TCA"}
          </button>
        </form>

        <div className="onboarding-footer">
          <p className="auth-footnote">
            Your identity stays attached to your account. It is not guessed
            from the recording.
          </p>

          <button
            type="button"
            className="onboarding-signout"
            onClick={signOut}
            disabled={busy}
          >
            Use a different account
          </button>
        </div>
      </section>
    </main>
  );
}
