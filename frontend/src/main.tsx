import { StrictMode, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";

import App from "./App";
import {
  clearAuthToken,
  getAuthToken,
  getCurrentUser,
} from "./api";
import { AuthScreen } from "./components/AuthScreen";
import "./styles.css";

function AuthGate() {
  const [checking, setChecking] = useState(true);
  const [authenticated, setAuthenticated] = useState(false);

  useEffect(() => {
    let active = true;

    async function checkSession() {
      if (!getAuthToken()) {
        if (active) {
          setAuthenticated(false);
          setChecking(false);
        }
        return;
      }

      try {
        await getCurrentUser();
        if (active) {
          setAuthenticated(true);
        }
      } catch {
        clearAuthToken();
        if (active) {
          setAuthenticated(false);
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
      setAuthenticated(false);
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

  if (!authenticated) {
    return <AuthScreen />;
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
