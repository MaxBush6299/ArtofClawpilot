import { Link, Outlet } from "react-router-dom";

export default function App() {
  return (
    <div className="layout">
      <header className="site-header">
        <Link to="/" className="brand">Art of Clawpilot</Link>
        <nav>
          <Link to="/">Gallery</Link>
          <Link to="/critic">Critic's Column</Link>
        </nav>
      </header>
      <main><Outlet /></main>
      <footer>
        <p>An AI-curated gallery. Curated daily by a Squad of three.</p>
      </footer>
    </div>
  );
}
