import { useState } from "react";

import {
  login,
  setAuthToken,
  signup,
} from "../api";
import type { AuthUser } from "../api";

type AuthMode = "login" | "signup";

type AuthScreenProps = {
  onAuthenticated: (user: AuthUser) => void;
};

export function AuthScreen({
  onAuthenticated,
}: AuthScreenProps) {
  const [mode, setMode] = useState<AuthMode>("login");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
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
      const result = mode === "signup"
        ? await signup(name, email, password)
        : await login(email, password);

      setAuthToken(result.access_token);
      onAuthenticated(result.user);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Could not complete authentication.",
      );
    } finally {
      setBusy(false);
    }
  }

  function switchMode(nextMode: AuthMode) {
    if (busy || nextMode === mode) {
      return;
    }

    setMode(nextMode);
    setError("");
    setPassword("");

    if (nextMode === "login") {
      setName("");
    }
  }

  return (
    <main className="auth-screen">
      <section className="auth-card" aria-labelledby="auth-title">
        <div className="auth-brand">
          <span className="auth-brand-mark">TCA</span>
          <span>The Call Assistant</span>
        </div>

        <div className="auth-copy">
          <span className="section-label">Private beta</span>
          <h1 id="auth-title">
            {mode === "login" ? "Welcome back." : "Start your TCA memory."}
          </h1>
          <p>Your conversations become useful memory.</p>
        </div>

        <div
          className="auth-tabs"
          role="tablist"
          aria-label="Authentication"
        >
          <button
            type="button"
            className={mode === "login" ? "active" : ""}
            onClick={() => switchMode("login")}
            role="tab"
            aria-selected={mode === "login"}
            aria-controls="auth-form"
            disabled={busy}
          >
            Log in
          </button>
          <button
            type="button"
            className={mode === "signup" ? "active" : ""}
            onClick={() => switchMode("signup")}
            role="tab"
            aria-selected={mode === "signup"}
            aria-controls="auth-form"
            disabled={busy}
          >
            Create account
          </button>
        </div>

        <form
          id="auth-form"
          className="auth-form"
          onSubmit={submit}
        >
          {mode === "signup" && (
            <label>
              <span>Name</span>
              <input
                value={name}
                onChange={(event) => setName(event.target.value)}
                autoComplete="name"
                placeholder="Your name"
                minLength={2}
                maxLength={120}
                required
                autoFocus
              />
            </label>
          )}

          <label>
            <span>Email</span>
            <input
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              autoComplete="email"
              placeholder="you@example.com"
              required
              autoFocus={mode === "login"}
            />
          </label>

          <label>
            <span>Password</span>
            <input
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              autoComplete={mode === "login" ? "current-password" : "new-password"}
              placeholder="At least 8 characters"
              minLength={8}
              maxLength={200}
              required
            />
          </label>

          {error && (
            <div className="auth-error" role="alert">
              {error}
            </div>
          )}

          <button
            className="auth-submit"
            type="submit"
            disabled={busy}
          >
            {busy
              ? mode === "login"
                ? "Signing in…"
                : "Creating account…"
              : mode === "login"
                ? "Log in"
                : "Create account"}
          </button>
        </form>

        <p className="auth-footnote">
          Your account keeps your saved conversations and identity separate from
          other private-beta users.
        </p>
      </section>
    </main>
  );
}
