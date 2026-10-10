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

function passwordStrength(value: string): number {
  let score = 0;
  if (value.length >= 12) score++;
  if (value.length >= 16) score++;
  if (/[a-z]/.test(value) && /[A-Z]/.test(value)) score++;
  if (/\d/.test(value) || /[^A-Za-z0-9]/.test(value)) score++;
  return Math.min(4, score);
}

export function AuthScreen({
  onAuthenticated,
}: AuthScreenProps) {
  const [mode, setMode] = useState<AuthMode>("login");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (busy) {
      return;
    }

    setError("");
    if (mode === "signup") {
      if (password !== confirmPassword) {
        setError("Your passwords don't match yet.");
        return;
      }
      if (passwordStrength(password) < 2) {
        setError("Choose a stronger password: use 12+ characters and combine word length with varied characters, or use a very long passphrase.");
        return;
      }
    }
    setBusy(true);

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
    setConfirmPassword("");
    setShowPassword(false);
    setShowConfirmPassword(false);

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

          <label className="password-field">
            <span>Password</span>
            <div className="password-input-row">
              <input
                type={showPassword ? "text" : "password"}
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                autoComplete={mode === "login" ? "current-password" : "new-password"}
                placeholder={mode === "signup" ? "Use a long, unique password" : "Your password"}
                minLength={12}
                maxLength={200}
                required
              />
              <button type="button" className="password-toggle" onClick={() => setShowPassword((value) => !value)} aria-label={showPassword ? "Hide password" : "Show password"}>{showPassword ? "Hide" : "Show"}</button>
            </div>
          </label>

          {mode === "signup" && password && (
            <div className="password-strength" aria-live="polite">
              <div className="password-strength-bars" aria-hidden="true">
                {[0, 1, 2, 3].map((bar) => <span key={bar} className={bar < passwordStrength(password) ? "filled" : ""} />)}
              </div>
              <span>{passwordStrength(password) <= 1 ? "Weak — use a longer passphrase" : passwordStrength(password) === 2 ? "Fair — make it longer or less predictable" : passwordStrength(password) === 3 ? "Good" : "Strong"}</span>
            </div>
          )}

          {mode === "signup" && (
            <label className="password-field">
              <span>Confirm password</span>
              <div className="password-input-row">
                <input
                  type={showConfirmPassword ? "text" : "password"}
                  value={confirmPassword}
                  onChange={(event) => setConfirmPassword(event.target.value)}
                  autoComplete="new-password"
                  placeholder="Enter your password again"
                  minLength={12}
                  maxLength={200}
                  required
                />
                <button type="button" className="password-toggle" onClick={() => setShowConfirmPassword((value) => !value)} aria-label={showConfirmPassword ? "Hide confirmation" : "Show confirmation"}>{showConfirmPassword ? "Hide" : "Show"}</button>
              </div>
              {confirmPassword && <small className={password === confirmPassword ? "password-match" : "password-mismatch"}>{password === confirmPassword ? "Passwords match" : "Passwords don't match yet"}</small>}
            </label>
          )}

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
