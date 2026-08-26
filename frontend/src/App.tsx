import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { createCall, getCalls } from "./api";
import type { Call } from "./api";

function formatDuration(seconds: number) {
  const totalSeconds = Math.round(seconds);
  const minutes = Math.floor(totalSeconds / 60);
  const remainingSeconds = totalSeconds % 60;

  if (minutes === 0) {
    return `${remainingSeconds}s`;
  }

  return `${minutes}m ${remainingSeconds}s`;
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat("en", {
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(new Date(value));
}

function App() {
  const [calls, setCalls] = useState<Call[]>([]);
  const [title, setTitle] = useState("");
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [message, setMessage] = useState("");

  async function loadCalls() {
    try {
      const result = await getCalls();
      setCalls(result);
      setMessage("");
    } catch (error) {
      setMessage(
        error instanceof Error
          ? error.message
          : "Could not load conversations."
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadCalls();
  }, []);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();

    if (creating) {
      return;
    }

    setCreating(true);
    setMessage("");

    try {
      const call = await createCall(title);

      setCalls((current) => [call, ...current]);
      setTitle("");

      setMessage(`Created "${call.title}".`);
    } catch (error) {
      setMessage(
        error instanceof Error
          ? error.message
          : "Could not create the call."
      );
    } finally {
      setCreating(false);
    }
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark">TCA</span>
          <span className="brand-name">The Call Assistant</span>
        </div>

        <span className="version">V0.2</span>
      </header>

      <section className="workspace">
        <div className="intro">
          <p className="eyebrow">New call</p>

          <h1>
            Keep track of what matters
            <br />
            in every call.
          </h1>

          <p className="intro-copy">
            Start when the call starts. Keep the important parts afterwards.
          </p>
        </div>

        <form className="call-composer" onSubmit={handleSubmit}>
          <label htmlFor="call-title">
            What is this call about?
          </label>

          <div className="composer-row">
            <input
              id="call-title"
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              placeholder="Product feedback with Jane"
              maxLength={120}
            />

            <button type="submit" disabled={creating}>
              {creating ? "Starting…" : "Start call"}
            </button>
          </div>
        </form>

        {message && (
          <p className="system-message">
            {message}
          </p>
        )}

        <section className="history">
          <div className="history-heading">
            <div>
              <p className="eyebrow">Recent conversations</p>
              <h2>Your calls</h2>
            </div>

            <span className="call-count">
              {calls.length}
            </span>
          </div>

          {loading ? (
            <p className="empty-state">
              Loading conversations…
            </p>
          ) : calls.length === 0 ? (
            <p className="empty-state">
              No calls yet. Your conversations will appear here.
            </p>
          ) : (
            <div className="call-list">
              {calls.map((call) => (
                <article className="call-row" key={call.id}>
                  <div className="call-date">
                    {formatDate(call.created_at)}
                  </div>

                  <div className="call-main">
                    <h3>{call.title}</h3>

                    <div className="call-meta">
                      <span>
                        {formatDuration(call.duration_seconds)}
                      </span>

                      <span className={`status status-${call.status}`}>
                        {call.status}
                      </span>
                    </div>
                  </div>

                  <button
                    className="open-call"
                    type="button"
                    aria-label={`Open ${call.title}`}
                  >
                    →
                  </button>
                </article>
              ))}
            </div>
          )}
        </section>
      </section>
    </main>
  );
}

export default App;