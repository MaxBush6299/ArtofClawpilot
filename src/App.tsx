import { Link, NavLink, Outlet } from "react-router-dom";

export default function App() {
  return (
    <div className="museum">
      <header className="site-header">
        <div className="header-inner">
          <Link to="/" className="brand">
            <span className="brand-mark">✦</span>
            <span className="brand-name">
              <span className="brand-line-1">The Clawpilot</span>
              <span className="brand-line-2">Museum of Modern Imagination</span>
            </span>
          </Link>
          <nav className="primary-nav">
            <NavLink to="/" end>Galleries</NavLink>
            <NavLink to="/critic">Critic's Column</NavLink>
          </nav>
        </div>
        <div className="header-rule" aria-hidden="true" />
      </header>
      <main className="museum-main">
        <Outlet />
      </main>
      <footer className="site-footer">
        <div className="footer-rule" aria-hidden="true" />
        <p className="footer-line">
          A living collection. Curated daily by a squad of three: an Artist, a Critic, and a Curator.
        </p>
        <p className="footer-fine">Established MMXXVI · Open daily at dawn</p>
      </footer>
    </div>
  );
}
