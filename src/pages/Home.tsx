import { Link } from "react-router-dom";
import gallery from "../../data/gallery.json";

export default function Home() {
  const rooms = gallery.rooms ?? [];
  return (
    <section className="home">
      <h1>The Collection</h1>
      <p className="lede">
        A growing, AI-generated gallery. Each morning, a new piece arrives.
      </p>
      <div className="room-grid">
        {rooms.map((r: any) => {
          const cover = r.images?.[0];
          return (
            <Link to={`/rooms/${r.id}`} key={r.id} className="room-card">
              {cover && <img src={cover.path} alt={cover.title} />}
              <div className="room-meta">
                <h2>{r.name}</h2>
                <p>{r.images?.length ?? 0} / 5 pieces</p>
              </div>
            </Link>
          );
        })}
      </div>
    </section>
  );
}
