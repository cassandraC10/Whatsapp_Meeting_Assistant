type Theme = "light" | "dark";

export function TopBar({
  theme,
  onToggleTheme,
  onCalls,
  onAsk,
  onPeople,
}: {
  theme: Theme;

  onToggleTheme:
    () => void;

  onCalls?:
    () => void;

  onAsk?:
    () => void;

  onPeople?:
    () => void;
}) {
  return (
    <header className="topbar">
      <div className="brand">
        <span className="brand-mark">
          TCA
        </span>

        <span className="brand-name">
          The Call Assistant
        </span>
      </div>

      <div className="topbar-actions">
        {onCalls && (
          <button
            type="button"
            className="topbar-nav-button"
            onClick={
              onCalls
            }
          >
            Calls
          </button>
        )}

        {onAsk && (
          <button
            type="button"
            className="topbar-nav-button"
            onClick={
              onAsk
            }
          >
            Ask TCA
          </button>
        )}

        {onPeople && (
          <button
            type="button"
            className="topbar-nav-button"
            onClick={
              onPeople
            }
          >
            People
          </button>
        )}

        <button
          className="theme-toggle"
          type="button"
          onClick={
            onToggleTheme
          }
          aria-label={
            theme === "dark"
              ? (
                "Switch to "
                + "light mode"
              )
              : (
                "Switch to "
                + "dark mode"
              )
          }
          title={
            theme === "dark"
              ? "Light mode"
              : "Dark mode"
          }
        >
          {theme === "dark"
            ? "☀"
            : "☾"}
        </button>

        <span className="version">
          V0.3
        </span>
      </div>
    </header>
  );
}


