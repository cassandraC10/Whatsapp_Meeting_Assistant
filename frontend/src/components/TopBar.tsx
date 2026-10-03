import { useEffect, useState } from "react";
import type {
  MouseEventHandler,
} from "react";

import {
  clearAuthToken,
  getCurrentUser,
} from "../api";

type Theme =
  | "light"
  | "dark";

type TopBarProps = {
  theme: Theme;
  onToggleTheme: MouseEventHandler<HTMLButtonElement>;
  onCalls?: () => void;
  onAsk?: () => void;
  onPeople?: () => void;
};

export function TopBar({
  theme,
  onToggleTheme,
  onCalls,
  onAsk,
  onPeople,
}: TopBarProps) {
  const [userName, setUserName] = useState("");

  useEffect(() => {
    let active = true;

    void getCurrentUser()
      .then((user) => {
        if (active) {
          setUserName(user.name);
        }
      })
      .catch(() => {
        // Auth expiry is handled centrally by the API client.
      });

    return () => {
      active = false;
    };
  }, []);

  function signOut() {
    clearAuthToken();
    window.dispatchEvent(new Event("tca-auth-expired"));
  }

  return (
    <header className="topbar">
      <button
        className="brand"
        type="button"
        onClick={onCalls}
        aria-label="Go to Calls"
      >
        <span className="brand-mark">
          TCA
        </span>

        <span className="brand-name">
          The Call Assistant
        </span>
      </button>

      <nav
        className="topbar-actions"
        aria-label="Primary navigation"
      >
        {onCalls && (
          <button
            className="topbar-nav-button"
            type="button"
            onClick={onCalls}
          >
            Calls
          </button>
        )}

        {onAsk && (
          <button
            className="topbar-nav-button"
            type="button"
            onClick={onAsk}
          >
            Ask TCA
          </button>
        )}

        {onPeople && (
          <button
            className="topbar-nav-button"
            type="button"
            onClick={onPeople}
          >
            People
          </button>
        )}

        {userName && (
          <span
            className="topbar-user"
            title="Your TCA identity"
          >
            <span className="topbar-user-dot" aria-hidden="true" />
            {userName}
          </span>
        )}

        <button
          className="theme-toggle"
          type="button"
          onClick={onToggleTheme}
          aria-label={
            theme === "dark"
              ? "Switch to light theme"
              : "Switch to dark theme"
          }
          title={
            theme === "dark"
              ? "Light theme"
              : "Dark theme"
          }
        >
          {theme === "dark"
            ? "☼"
            : "◐"}
        </button>

        <button
          className="topbar-nav-button topbar-signout"
          type="button"
          onClick={signOut}
        >
          Sign out
        </button>

        <span
          className="version"
          aria-label="TCA version 0.5"
        >
          v0.5
        </span>
      </nav>
    </header>
  );
}
