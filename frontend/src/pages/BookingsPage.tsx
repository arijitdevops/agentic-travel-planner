import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import StatusBadge from "../components/StatusBadge";
import { money } from "../lib/format";
import type { Booking } from "../types";

export default function BookingsPage() {
  const [bookings, setBookings] = useState<Booking[] | null>(null);
  const [filter, setFilter] = useState<"" | "confirmed" | "cancelled">("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  useEffect(() => {
    api.bookings(filter ? { status: filter } : {}).then(setBookings).catch((e: Error) => setError(e.message));
  }, [filter]);

  async function cancel(b: Booking) {
    if (!confirm(`Cancel booking ${b.reference}?`)) return;
    setBusy(b.reference);
    try {
      const updated = await api.cancelBooking(b.reference);
      setBookings((list) => list?.map((x) => (x.id === updated.id ? updated : x)) ?? null);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(null);
    }
  }

  return (
    <div>
      <div className="page-head">
        <h1>My bookings</h1>
        <div className="segmented">
          {(["", "confirmed", "cancelled"] as const).map((f) => (
            <button key={f || "all"} className={filter === f ? "on" : ""} onClick={() => setFilter(f)}>
              {f || "all"}
            </button>
          ))}
        </div>
      </div>
      <div className="alert alert-info small">
        Bookings are simulated: they hold inventory in this app's database but no payment is taken and no real tickets are issued.
      </div>
      {error && <div className="alert alert-error">{error}</div>}
      {!bookings ? (
        <div className="loading">Loading bookings...</div>
      ) : bookings.length === 0 ? (
        <div className="empty card">
          <h3>No bookings</h3>
          <p className="muted">
            Book flights and hotels from a <Link to="/trips">trip plan</Link> or search them <Link to="/explore">directly</Link>.
          </p>
        </div>
      ) : (
        <div className="booking-list">
          {bookings.map((b) => (
            <div key={b.id} className={`card booking-row ${b.status}`}>
              <div className="booking-kind">{b.kind === "flight" ? "✈" : "\u{1F3E8}"}</div>
              <div className="booking-body">
                <div className="row">
                  <span className="pnr-small">{b.reference}</span>
                  <StatusBadge status={b.status} />
                  {b.trip_id && <Link className="small" to={`/trips/${b.trip_id}`}>View trip</Link>}
                </div>
                <div className="strong">{b.summary}</div>
                <div className="muted small">
                  {b.travelers.map((t) => `${t.first_name} ${t.last_name}${t.ticket_number ? ` (${t.ticket_number})` : ""}`).join(", ")}
                </div>
                <div className="muted small">
                  Booked {new Date(b.created_at + "Z").toLocaleString()} &middot; {b.contact_email}
                  {b.status === "cancelled" && b.refund_amount !== null && ` · refund ${money(b.refund_amount, b.currency, 2)}`}
                </div>
              </div>
              <div className="booking-side">
                <div className="price">{money(b.total_price, b.currency, 2)}</div>
                {b.status === "confirmed" && (
                  <button className="btn btn-danger-ghost btn-small" disabled={busy === b.reference} onClick={() => cancel(b)}>
                    {busy === b.reference ? "Cancelling..." : "Cancel"}
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
