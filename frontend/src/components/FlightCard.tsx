import { cabinLabel, clock, dayOffset, duration, money, shortDate, stopsLabel } from "../lib/format";
import type { FlightOffer } from "../types";

interface Props {
  offer: FlightOffer;
  recommended?: boolean;
  booked?: boolean;
  onBook?: (offer: FlightOffer) => void;
}

export default function FlightCard({ offer, recommended, booked, onBook }: Props) {
  const plus = dayOffset(offer.departure, offer.arrival);
  return (
    <div className={`offer-card ${recommended ? "offer-recommended" : ""}`}>
      {recommended && <span className="ribbon">Agent's pick</span>}
      <div className="flight-main">
        <div className="airline">
          <span className="airline-logo">{offer.airline_code}</span>
          <div>
            <div className="strong">{offer.airline_name}</div>
            <div className="muted small">
              {offer.flight_number} &middot; {offer.aircraft ?? "Aircraft TBC"}
            </div>
          </div>
        </div>
        <div className="flight-times">
          <div>
            <div className="time">{clock(offer.departure)}</div>
            <div className="muted small">{offer.origin}</div>
          </div>
          <div className="flight-line">
            <span className="small muted">{duration(offer.duration_minutes)}</span>
            <span className="line" />
            <span className={`small ${offer.stops ? "warn-text" : "ok-text"}`}>{stopsLabel(offer.stops, offer.via)}</span>
          </div>
          <div>
            <div className="time">
              {clock(offer.arrival)}
              {plus > 0 && <sup>+{plus}</sup>}
            </div>
            <div className="muted small">{offer.destination}</div>
          </div>
        </div>
        <div className="price-block">
          <div className="price">{money(offer.total_price, offer.currency)}</div>
          <div className="muted small">
            {offer.adults + offer.children} traveler{offer.adults + offer.children > 1 ? "s" : ""} &middot; {cabinLabel(offer.cabin_class)}
          </div>
          {onBook &&
            (booked ? (
              <span className="badge badge-confirmed">Booked</span>
            ) : (
              <button className="btn btn-primary btn-small" onClick={() => onBook(offer)}>
                Book
              </button>
            ))}
        </div>
      </div>
      <div className="offer-meta small muted">
        <span>{shortDate(offer.departure)}</span>
        <span>{offer.baggage}</span>
        <span>{offer.refundable ? "Refundable" : "Non-refundable after 24h"}</span>
        {offer.seats_left !== null && offer.seats_left < 10 && <span className="warn-text">Only {offer.seats_left} seats left</span>}
      </div>
    </div>
  );
}
