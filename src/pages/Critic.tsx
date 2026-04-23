import critiques from "../../data/critiques.json";

export default function Critic() {
  const items = ((critiques.entries ?? []) as any[]).slice().reverse();

  return (
    <section className="critic-column">
      <header className="column-masthead">
        <p className="masthead-kicker">The Daily Column</p>
        <h1 className="masthead-title">The Critic's Column</h1>
        <p className="masthead-rule" aria-hidden="true" />
        <p className="masthead-tag">
          A daily reflection on the museum's newest arrival — opinionated, but fair.
        </p>
      </header>

      {items.length === 0 && (
        <p className="empty-column">
          The presses are warm but no ink has yet been spilled. The first column
          will appear with the first piece.
        </p>
      )}

      <div className="column-feed">
        {items.map((c: any, idx: number) => (
          <article key={c.id} className="critique-entry">
            <p className="entry-date">
              {new Date(c.date).toLocaleDateString(undefined, { weekday: "long", year: "numeric", month: "long", day: "numeric" })}
            </p>
            <h2 className="entry-title">{c.title}</h2>
            {c.themes && c.themes.length > 0 && (
              <p className="entry-themes">
                {c.themes.map((t: string) => (
                  <span key={t} className="theme-pill">{t}</span>
                ))}
              </p>
            )}
            <div className="entry-body">
              {c.body.split(/\n\n+/).map((para: string, i: number) => (
                <p key={i}>{para}</p>
              ))}
            </div>
            {c.suggestion && (
              <p className="suggestion">
                <span className="suggestion-label">For tomorrow —</span> {c.suggestion}
              </p>
            )}
            {idx < items.length - 1 && <hr className="entry-divider" />}
          </article>
        ))}
      </div>
    </section>
  );
}
