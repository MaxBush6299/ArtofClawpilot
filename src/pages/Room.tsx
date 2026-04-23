import { useState } from "react";
import { useParams, Link } from "react-router-dom";
import gallery from "../../data/gallery.json";

export default function Room() {
  const { roomId } = useParams();
  const room = ((gallery.rooms ?? []) as any[]).find((r) => r.id === roomId);
  const [lightbox, setLightbox] = useState<any | null>(null);

  if (!room) {
    return (
      <section className="room">
        <p className="not-found">
          This gallery is closed for the day. <Link to="/">Return to the lobby →</Link>
        </p>
      </section>
    );
  }

  const images = (room.images ?? []) as any[];

  return (
    <section className="room">
      <Link to="/" className="back-link">← Back to galleries</Link>

      <div className="room-header">
        <p className="eyebrow">Gallery</p>
        <h1 className="room-title">{room.name}</h1>
        {room.theme && <p className="room-lede">{room.theme}</p>}
      </div>

      {images.length === 0 ? (
        <div className="empty-hall">
          <p>This hall awaits its first piece. Please return at dawn.</p>
        </div>
      ) : (
        <div className="image-grid">
          {images.map((img) => (
            <figure key={img.id} className="piece">
              <button
                type="button"
                className="frame-button"
                onClick={() => setLightbox(img)}
                aria-label={`View ${img.title} larger`}
              >
                <div className="frame">
                  <div className="mat">
                    <img src={img.path} alt={img.title} />
                  </div>
                </div>
              </button>
              <figcaption className="plaque">
                <h3 className="plaque-title">{img.title}</h3>
                <p className="plaque-meta">
                  AI Artist · {new Date(img.createdAt).toLocaleDateString(undefined, { year: "numeric", month: "long", day: "numeric" })}
                </p>
                {img.artistNote && <p className="artist-note">{img.artistNote}</p>}
                {img.criticism && (
                  <blockquote className="critique">
                    <span className="quote-mark" aria-hidden="true">“</span>
                    {img.criticism}
                  </blockquote>
                )}
              </figcaption>
            </figure>
          ))}
        </div>
      )}

      {lightbox && (
        <div
          className="lightbox"
          role="dialog"
          aria-modal="true"
          aria-label={lightbox.title}
          onClick={() => setLightbox(null)}
        >
          <button
            type="button"
            className="lightbox-close"
            onClick={() => setLightbox(null)}
            aria-label="Close"
          >
            ×
          </button>
          <div className="lightbox-frame" onClick={(e) => e.stopPropagation()}>
            <div className="frame frame-lg">
              <div className="mat">
                <img src={lightbox.path} alt={lightbox.title} />
              </div>
            </div>
            <p className="lightbox-caption">{lightbox.title}</p>
          </div>
        </div>
      )}
    </section>
  );
}
