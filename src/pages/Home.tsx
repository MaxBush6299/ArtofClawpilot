import { Link } from "react-router-dom";
import gallery from "../../data/gallery.json";

export default function Home() {
  const rooms = (gallery.rooms ?? []) as any[];
  const totalPieces = rooms.reduce((n, r) => n + (r.images?.length ?? 0), 0);

  return (
    <section className="home">
      <div className="hero">
        <p className="eyebrow">Now on view</p>
        <h1 className="hero-title">The Permanent Collection</h1>
        <p className="hero-lede">
          A living museum of works generated each morning at first light.
          Three custodians — an Artist, a Critic, and a Curator — tend the halls
          and admit one new piece per day.
        </p>
        <dl className="hero-stats">
          <div><dt>Galleries</dt><dd>{rooms.length}</dd></div>
          <div><dt>Works on view</dt><dd>{totalPieces}</dd></div>
          <div><dt>Admission</dt><dd>Free</dd></div>
        </dl>
      </div>

      <div className="section-heading">
        <span className="section-rule" aria-hidden="true" />
        <h2>Galleries</h2>
        <span className="section-rule" aria-hidden="true" />
      </div>

      <div className="room-grid">
        {rooms.map((r) => {
          const cover = r.images?.[0];
          const count = r.images?.length ?? 0;
          return (
            <Link to={`/rooms/${r.id}`} key={r.id} className="room-card">
              <div className="room-cover">
                {cover ? (
                  <div className="room-frame">
                    <img src={cover.path} alt={cover.title} />
                  </div>
                ) : (
                  <div className="room-empty">
                    <span>Awaiting<br />first acquisition</span>
                  </div>
                )}
              </div>
              <div className="room-meta">
                <h3>{r.name}</h3>
                {r.theme && <p className="room-theme">{r.theme}</p>}
                <p className="room-count">
                  {count} of 5 works · <span className="room-link">Enter gallery →</span>
                </p>
              </div>
            </Link>
          );
        })}
      </div>
    </section>
  );
}
