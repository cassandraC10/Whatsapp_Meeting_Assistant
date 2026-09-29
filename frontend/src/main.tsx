import { StrictMode, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";

import App from "./App";
import {
  clearAuthToken,
  getAuthToken,
  getCurrentUser,
} from "./api";
import type { AuthUser } from "./api";
import { AuthScreen } from "./components/AuthScreen";
import { OnboardingScreen } from "./components/OnboardingScreen";
import "./styles.css";

function AuthGate() {
  const [checking, setChecking] = useState(true);
  const [user, setUser] = useState<AuthUser | null>(null);

  useEffect(() => {
    let active = true;

    async function checkSession() {
      if (!getAuthToken()) {
        if (active) {
          setUser(null);
          setChecking(false);
        }
        return;
      }

      try {
        const currentUser = await getCurrentUser();
        if (active) {
          setUser(currentUser);
        }
      } catch {
        clearAuthToken();
        if (active) {
          setUser(null);
        }
      } finally {
        if (active) {
          setChecking(false);
        }
      }
    }

    void checkSession();

    function handleAuthExpired() {
      clearAuthToken();
      setUser(null);
    }

    window.addEventListener("tca-auth-expired", handleAuthExpired);

    return () => {
      active = false;
      window.removeEventListener("tca-auth-expired", handleAuthExpired);
    };
  }, []);

  if (checking) {
    return (
      <main className="auth-screen auth-loading">
        <div className="auth-loading-mark">TCA</div>
        <p>Checking your account…</p>
      </main>
    );
  }

  if (!user) {
    return <AuthScreen />;
  }

  if (!user.onboarding_completed) {
    return (
      <OnboardingScreen
        user={user}
        onComplete={setUser}
      />
    );
  }

  return <App />;
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <AuthGate />
  </StrictMode>,
);

if (import.meta.env.PROD && "serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    void navigator.serviceWorker.register("/sw.js");
  });
}
