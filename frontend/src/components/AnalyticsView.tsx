import type { AnalyticsResponse } from "../api";

type AnalyticsViewProps = {
  analytics: AnalyticsResponse | null;
  loading: boolean;
  error: string;
  days: number;
  onDaysChange: (days: number) => void;
  onRefresh: () => void;
  onBack: () => void;
  theme: "light" | "dark";
  onToggleTheme: () => void;
  onCalls: () => void;
  onAsk: () => void;
  onPeople: () => void;
};

function formatNumber(value: number): string {
  return new Intl.NumberFormat("en-US").format(value);
}

function formatDuration(seconds: number): string {
  const rounded = Math.max(0, Math.round(seconds));
  const minutes = Math.floor(rounded / 60);
  const remaining = rounded % 60;
  if (minutes === 0) {
    return `${remaining}s`;
  }
  return `${minutes}m ${remaining}s`;
}

function formatCost(value: number | null): string {
  if (value === null) {
    return "Not configured";
  }
  return `$${value.toFixed(4)}`;
}

export function AnalyticsView({
  analytics,
  loading,
  error,
  days,
  onDaysChange,
  onRefresh,
  onBack,
  theme,
  onToggleTheme,
  onCalls,
  onAsk,
  onPeople,
}: AnalyticsViewProps) {
  return (
    <div className="app-shell">
      <header className="analytics-header">
        <div>
          <button
            type="button"
            className="secondary-button analytics-back"
            onClick={onBack}
          >
            ← Back to Calls
          </button>
          <span className="section-label">Private beta</span>
          <h1>Your TCA analytics</h1>
          <p>
            A lightweight view of how you use capture, memory, feedback, and AI.
          </p>
        </div>

        <div className="analytics-header-actions">
          <label className="analytics-period">
            <span>Period</span>
            <select
              value={days}
              onChange={(event) => onDaysChange(Number(event.target.value))}
            >
              <option value={7}>7 days</option>
              <option value={30}>30 days</option>
              <option value={90}>90 days</option>
            </select>
          </label>
          <button
            type="button"
            className="secondary-button"
            onClick={onRefresh}
            disabled={loading}
          >
            {loading ? "Refreshing…" : "Refresh"}
          </button>
        </div>
      </header>

      <div className="analytics-nav-shell">
        <div className="analytics-nav">
          <button type="button" onClick={onCalls}>Calls</button>
          <button type="button" onClick={onAsk}>Ask TCA</button>
          <button type="button" onClick={onPeople}>People</button>
          <button type="button" onClick={onToggleTheme}>
            {theme === "dark" ? "Light" : "Dark"}
          </button>
        </div>
      </div>

      {error && (
        <div className="notice notice-error analytics-error" role="alert">
          {error}
        </div>
      )}

      {loading && !analytics ? (
        <div className="analytics-loading">
          Loading your analytics…
        </div>
      ) : analytics ? (
        <main className="analytics-grid">
          <section className="analytics-card analytics-card-wide">
            <span className="section-label">Usage</span>
            <div className="analytics-metric-grid">
              <div className="analytics-metric">
                <strong>{formatNumber(analytics.overview.active_days)}</strong>
                <span>Active days</span>
              </div>
              <div className="analytics-metric">
                <strong>{formatNumber(analytics.overview.conversation_events)}</strong>
                <span>Conversations touched</span>
              </div>
              <div className="analytics-metric">
                <strong>{formatNumber(analytics.overview.capture_opens)}</strong>
                <span>Capture opens</span>
              </div>
              <div className="analytics-metric">
                <strong>{formatDuration(analytics.overview.recording_seconds)}</strong>
                <span>Recording time</span>
              </div>
            </div>
          </section>

          <section className="analytics-card">
            <span className="section-label">Processing</span>
            <div className="analytics-big-number">
              {analytics.processing.success_rate === null
                ? "—"
                : `${analytics.processing.success_rate}%`}
            </div>
            <p>Processing success rate</p>
            <div className="analytics-stat-list">
              <span>Started <strong>{analytics.processing.started}</strong></span>
              <span>Completed <strong>{analytics.processing.completed}</strong></span>
              <span>Failed <strong>{analytics.processing.failed}</strong></span>
            </div>
          </section>

          <section className="analytics-card">
            <span className="section-label">Feedback</span>
            <div className="analytics-big-number">
              {analytics.overview.feedback_helpful_rate === null
                ? "—"
                : `${analytics.overview.feedback_helpful_rate}%`}
            </div>
            <p>Helpful feedback rate</p>
            <div className="analytics-stat-list">
              <span>Helpful <strong>{analytics.overview.feedback_helpful}</strong></span>
              <span>Needs work <strong>{analytics.overview.feedback_needs_work}</strong></span>
              <span>Updates <strong>{analytics.overview.feedback_updated}</strong></span>
            </div>
          </section>

          <section className="analytics-card analytics-card-wide">
            <span className="section-label">AI usage</span>
            <div className="analytics-ai-summary">
              <div>
                <strong>{formatNumber(analytics.ai_usage.total_tokens)}</strong>
                <span>Total tokens</span>
              </div>
              <div>
                <strong>{formatNumber(analytics.ai_usage.requests)}</strong>
                <span>AI requests</span>
              </div>
              <div>
                <strong>{formatCost(analytics.ai_usage.estimated_cost_usd)}</strong>
                <span>Estimated cost</span>
              </div>
            </div>
            <p className="analytics-muted">
              Model: {analytics.ai_usage.model}. Cost is estimated only when
              Gemini pricing is configured on the backend.
            </p>
            <div className="analytics-operation-list">
              {analytics.ai_usage.by_operation.length === 0 ? (
                <span className="analytics-muted">No AI usage recorded in this period.</span>
              ) : (
                analytics.ai_usage.by_operation.map((operation) => (
                  <div key={operation.operation} className="analytics-operation-row">
                    <strong>{operation.operation.replaceAll("_", " ")}</strong>
                    <span>{formatNumber(operation.requests)} requests</span>
                    <span>{formatNumber(operation.total_tokens)} tokens</span>
                    <span>{formatCost(operation.estimated_cost_usd)}</span>
                  </div>
                ))
              )}
            </div>
          </section>

          <section className="analytics-card analytics-card-wide">
            <span className="section-label">Product signals</span>
            <div className="analytics-event-list">
              {analytics.events.map((event) => (
                <div key={event.event_name} className="analytics-event-row">
                  <span>{event.event_name.replaceAll("_", " ")}</span>
                  <strong>{formatNumber(event.count)}</strong>
                </div>
              ))}
            </div>
          </section>
        </main>
      ) : null}
    </div>
  );
}
