import type { Call } from "../api";

function formatDuration(seconds: number) {
  const totalSeconds = Math.max(0, Math.round(seconds));
  const minutes = Math.floor(totalSeconds / 60);
  const remainingSeconds = totalSeconds % 60;
  if (minutes === 0) return `${remainingSeconds}s`;
  return `${minutes}m ${remainingSeconds}s`;
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat("en", { day: "numeric", month: "short", year: "numeric" }).format(new Date(value));
}

export function CallRow({
  call,
  onOpen,
}: {
  call: Call;
  onOpen: () => void;
}) {
  return (
    <button
      type="button"
      className="call-row"
      onClick={
        onOpen
      }
    >
      <div className="call-date">
        {formatDate(
          call.created_at
        )}
      </div>

      <div className="call-main">
        <h3>
          {call.title}
        </h3>

        <div className="call-meta">
          <span>
            {formatDuration(
              call.duration_seconds
            )}
          </span>

          <span
            className={
              `status `
              + `status-${
                call.status
              }`
            }
          >
            {call.status}
          </span>
        </div>
      </div>

      <span className="call-arrow">
        →
      </span>
    </button>
  );
}