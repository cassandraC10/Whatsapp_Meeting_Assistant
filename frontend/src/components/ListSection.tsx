export function ListSection({
  title,
  items,
}: {
  title: string;
  items: string[];
}) {
  if (
    items.length === 0
  ) {
    return null;
  }

  return (
    <section className="recap-section">
      <h2>
        {title}
      </h2>

      <ul className="note-list">
        {items.map(
          (
            item,
            index
          ) => (
            <li
              key={
                index
              }
            >
              {item}
            </li>
          )
        )}
      </ul>
    </section>
  );
}

