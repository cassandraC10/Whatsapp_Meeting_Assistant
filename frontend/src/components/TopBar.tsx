import type {
  MouseEventHandler,
} from "react";

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

        <span
          className="version"
          aria-label="TCA version 0.4"
        >
          v0.4
        </span>
      </nav>
    </header>
  );
}
