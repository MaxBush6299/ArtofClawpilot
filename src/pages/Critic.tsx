import critiques from "../../data/critiques.json";

export default function Critic() {
  const items = critiques.entries ?? [];
  return (
    <section className="critic-column">
      <h1>The Critic's Column</h1>
      <p className="lede">A daily reflection on the gallery's newest arrival.</p>
      {items.length === 0 && <p>No critiques yet. Check back tomorrow.</p>}
      {items.slice().reverse().map((c: any) => (
        <article key={c.id} className="critique-entry">
          <header>
            <h2>{c.title}</h2>
            <small>{new Date(c.date).toLocaleDateString()}</small>
          </header>
          <p><strong>Themes:</strong> {(c.themes ?? []).join(", ")}</p>
          <p>{c.body}</p>
          <p className="suggestion"><em>Suggested next:</em> {c.suggestion}</p>
        </article>
      ))}
    </section>
  );
}
