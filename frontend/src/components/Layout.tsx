import { useEffect, useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { api, getUserEmail, setUserEmail } from "../api/client";
import type { Health, User } from "../types";

export default function Layout() {
  const [health, setHealth] = useState<Health | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [editing, setEditing] = useState(false);
  const [emailDraft, setEmailDraft] = useState(getUserEmail() ?? "");

  useEffect(() => {
    api.health().then(setHealth).catch(() => setHealth(null));
    api.me().then(setUser).catch(() => setUser(null));
  }, []);

  function switchUser(e: React.FormEvent) {
    e.preventDefault();
    setUserEmail(emailDraft.trim() || null);
    window.location.reload();
  }

  return (
    <div className="app">
      <header className="topbar">
        <div className="topbar-inner">
          <NavLink to="/" className="brand">
            <span className="brand-mark" aria-hidden>
              <svg viewBox="0 0 24 24" width="18" height="18"><path d="M3 14l18-7-5 11-3-4-4 3 1-4z" fill="currentColor" /></svg>
            </span>
            Agentic Travel Planner
          </NavLink>
          <nav className="nav">
            <NavLink to="/" end>Plan a trip</NavLink>
            <NavLink to="/trips">My trips</NavLink>
            <NavLink to="/explore">Flights &amp; hotels</NavLink>
            <NavLink to="/bookings">My bookings</NavLink>
          </nav>
          <div className="topbar-right">
            {health && (
              <span className={`pill ${health.llm_configured ? "pill-ok" : "pill-warn"}`} title={health.llm_model}>
                {health.llm_configured ? "AI agents online" : "AI offline - no API key"}
              </span>
            )}
            {editing ? (
              <form onSubmit={switchUser} className="user-form">
                <input type="email" placeholder="you@example.com" value={emailDraft} onChange={(e) => setEmailDraft(e.target.value)} autoFocus />
                <button className="btn btn-small" type="submit">Switch</button>
              </form>
            ) : (
              <button className="user-chip" onClick={() => setEditing(true)} title="Switch traveler">
                <span className="avatar">{(user?.name ?? "?").slice(0, 1).toUpperCase()}</span>
                <span className="user-name">{user?.name ?? "Guest"}</span>
              </button>
            )}
          </div>
        </div>
      </header>
      {health && !health.llm_configured && (
        <div className="banner banner-warn">
          <strong>GEMINI_API_KEY is not configured.</strong> Trip planning by the AI agents is disabled, but you can still search and book
          flights and hotels. Add a key to <code>backend/.env</code> and restart the API.
        </div>
      )}
      <main className="container">
        <Outlet />
      </main>
      <footer className="footer">
        Bookings are simulated for demonstration purposes - no payment is taken and no real tickets are issued.
      </footer>
    </div>
  );
}
