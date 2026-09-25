import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { cabinLabel, clock, money, shortDate } from "../lib/format";
import type { Booking, FlightOffer, HotelOffer, TravelerInput } from "../types";

export type BookableOffer = { kind: "flight"; offer: FlightOffer } | { kind: "hotel"; offer: HotelOffer };

interface Props {
  item: BookableOffer;
  tripId?: number | null;
  onClose: () => void;
  onBooked?: (booking: Booking) => void;
}

function blankTravelers(item: BookableOffer): TravelerInput[] {
  if (item.kind === "flight") {
    return [
      ...Array.from({ length: item.offer.adults }, () => ({ first_name: "", last_name: "", traveler_type: "adult" as const })),
      ...Array.from({ length: item.offer.children }, () => ({ first_name: "", last_name: "", traveler_type: "child" as const, date_of_birth: "" })),
    ];
  }
  return Array.from({ length: item.offer.guests }, () => ({ first_name: "", last_name: "", traveler_type: "adult" as const }));
}

export default function BookingDialog({ item, tripId, onClose, onBooked }: Props) {
  const [quote, setQuote] = useState<BookableOffer | null>(null);
  const [quoteError, setQuoteError] = useState<string | null>(null);
  const [travelers, setTravelers] = useState<TravelerInput[]>(() => blankTravelers(item));
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [booking, setBooking] = useState<Booking | null>(null);

  // Re-price the offer: fares and availability can change after the plan was made.
  useEffect(() => {
    const load =
      item.kind === "flight"
        ? api.flightOffer(item.offer.id).then((offer) => ({ kind: "flight" as const, offer }))
        : api.hotelOffer(item.offer.id).then((offer) => ({ kind: "hotel" as const, offer }));
    load.then(setQuote).catch((e: Error) => setQuoteError(e.message));
  }, [item]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const update = (i: number, patch: Partial<TravelerInput>) =>
    setTravelers((ts) => ts.map((t, idx) => (idx === i ? { ...t, ...patch } : t)));

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const result = await api.book({
        offer_id: item.offer.id,
        trip_id: tripId ?? null,
        contact_email: email,
        contact_phone: phone || undefined,
        travelers: travelers.map((t) => ({ ...t, date_of_birth: t.date_of_birth || null })),
      });
      setBooking(result);
      onBooked?.(result);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSubmitting(false);
    }
  }

  const current = quote ?? item;
  const priceChanged = quote && Math.abs(quote.offer.total_price - item.offer.total_price) > 0.01;

  return (
    <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal" role="dialog" aria-modal="true" aria-labelledby="booking-title">
        <button className="modal-close" onClick={onClose} aria-label="Close">&times;</button>
        {booking ? (
          <div className="confirmation">
            <div className="confirm-icon">{"✓"}</div>
            <h2 id="booking-title">Booking confirmed</h2>
            <p className="muted">Reference</p>
            <div className="pnr">{booking.reference}</div>
            <p>{booking.summary}</p>
            <p className="strong">{money(booking.total_price, booking.currency, 2)}</p>
            <p className="muted small">Simulated booking - no payment was taken and no real ticket was issued.</p>
            <div className="row center">
              <Link className="btn" to="/bookings" onClick={onClose}>View my bookings</Link>
              <button className="btn btn-primary" onClick={onClose}>Done</button>
            </div>
          </div>
        ) : (
          <form onSubmit={submit}>
            <h2 id="booking-title">{item.kind === "flight" ? "Book flight" : "Book hotel"}</h2>
            <div className="quote-box">
              {current.kind === "flight" ? (
                <div>
                  <div className="strong">
                    {current.offer.airline_name} {current.offer.flight_number} &middot; {current.offer.origin_city} to {current.offer.destination_city}
                  </div>
                  <div className="muted small">
                    {shortDate(current.offer.departure)}, {clock(current.offer.departure)} - {clock(current.offer.arrival)} &middot; {cabinLabel(current.offer.cabin_class)}
                  </div>
                </div>
              ) : (
                <div>
                  <div className="strong">{current.offer.name}</div>
                  <div className="muted small">
                    {current.offer.rooms} x {current.offer.room_name} &middot; {shortDate(current.offer.check_in)} - {shortDate(current.offer.check_out)}
                  </div>
                </div>
              )}
              <div className="price">{money(current.offer.total_price, current.offer.currency, 2)}</div>
            </div>
            {!quote && !quoteError && <p className="muted small">Checking the latest price and availability...</p>}
            {priceChanged && (
              <div className="alert alert-warn">
                The price changed since this plan was created (was {money(item.offer.total_price, item.offer.currency, 2)}).
              </div>
            )}
            {quoteError && <div className="alert alert-error">{quoteError}</div>}

            <h3>{item.kind === "flight" ? "Passengers" : "Guests"}</h3>
            <p className="muted small">Names must match the travel documents.</p>
            {travelers.map((t, i) => (
              <div className="traveler-row" key={i}>
                <span className="traveler-type">{t.traveler_type === "child" ? "Child" : "Adult"} {i + 1}</span>
                <input required placeholder="First name" value={t.first_name} onChange={(e) => update(i, { first_name: e.target.value })} />
                <input required placeholder="Last name" value={t.last_name} onChange={(e) => update(i, { last_name: e.target.value })} />
                {t.traveler_type === "child" && (
                  <input type="date" aria-label="Date of birth" value={t.date_of_birth ?? ""} onChange={(e) => update(i, { date_of_birth: e.target.value })} />
                )}
              </div>
            ))}
            <h3>Contact</h3>
            <div className="grid-2">
              <input required type="email" placeholder="Email for confirmation" value={email} onChange={(e) => setEmail(e.target.value)} />
              <input placeholder="Phone (optional)" value={phone} onChange={(e) => setPhone(e.target.value)} />
            </div>
            <div className="alert alert-info small">
              This is a demo booking flow: the booking is recorded and inventory is held, but no payment is taken.
            </div>
            {error && <div className="alert alert-error">{error}</div>}
            <div className="form-actions">
              <button type="button" className="btn" onClick={onClose}>Cancel</button>
              <button className="btn btn-primary" disabled={submitting || !!quoteError || !quote}>
                {submitting ? "Booking..." : `Confirm ${money(current.offer.total_price, current.offer.currency, 2)}`}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
