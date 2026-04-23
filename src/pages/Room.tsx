import { useParams, Link } from "react-router-dom";
import gallery from "../../data/gallery.json";

export default function Room() {
  const { roomId } = useParams();
  const room = (gallery.rooms ?? []).find((r: any) => r.id === roomId);
  if (!room) return <p>Room not found. <Link to="/">Back to gallery</Link></p>;

  return (
    <section className="room">
      <Link to="/">← All rooms</Link>
      <h1>{room.name}</h1>
      {room.theme && <p className="lede">{room.theme}</p>}
      <div className="image-grid">
        {(room.images ?? []).map((img: any) => (
          <figure key={img.id} className="piece">
            <img src={img.path} alt={img.title} />
            <figcaption>
              <h3>{img.title}</h3>
              <p className="artist-note">{img.artistNote}</p>
              {img.criticism && (
                <blockquote className="critique">{img.criticism}</blockquote>
              )}
              <small>{new Date(img.createdAt).toLocaleDateString()}</small>
            </figcaption>
          </figure>
        ))}
      </div>
    </section>
  );
}
