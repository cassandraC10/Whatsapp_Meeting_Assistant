export function AskTcaEntry({
  onOpen,
}: {
  onOpen: () => void;
}) {
  return (
    <section className="ask-entry">
      <div className="ask-entry-copy">
        <span className="section-label">
          Ask TCA
        </span>

        <h2>
          What do you want to remember?
        </h2>

        <p>
          Ask a question across your
          saved conversations.
        </p>
      </div>

      <button
        type="button"
        className="secondary-button"
        onClick={
          onOpen
        }
      >
        Ask TCA
      </button>
    </section>
  );
}


