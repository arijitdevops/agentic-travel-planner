import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import StatusBadge from "../components/StatusBadge";
import { dateRange, money, nightsBetween } from "../lib/format";
import type { TripSummary } from "../types";

export default function TripsPage() {
  const [trips, setTrips] = useState<TripSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.trips().then(setTrips).catch((e: Error) => setError(e.message));
  }, []);

  if (error) return <div className="alert alert-error">{error}</div>;
  if (!trips) return <div className="loading">Loading trips...</div>;

  return (
    <div>
      <div className="page-head">
        <h1>My trips</h1>
        <Link to="/" className="btn btn-primary">Plan a new trip</Link>
      </div>
      {trips.length === 0 ? (
        <div className="empty card">
          <h3>No trips yet</h3>
          <p className="muted">Tell the agents where you want to go and they will build a complete plan.</p>
        </div>
      ) : (
        <div className="trip-grid">
          {trips.map((t) => (
            <Link to={`/trips/${t.id}`} key={t.id} className="card trip-tile">
              <div className="row between">
                <span className="route">{[t.origin, ...t.destinations, t.origin].join(" → ")}</span>
                <StatusBadge status={t.status} />
              </div>
              <h3>{t.title}</h3>
              <p className="muted small">
                {dateRange(t.start_date, t.end_date)} &middot; {nightsBetween(t.start_date, t.end_date)} nights &middot; {t.adults + t.children} travelers
              </p>
              <p className="small">Budget {money(t.budget, t.currency)}</p>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
