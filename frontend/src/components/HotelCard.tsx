import { money } from "../lib/format";
import type { HotelOffer } from "../types";

interface Props {
  offer: HotelOffer;
  recommended?: boolean;
  booked?: boolean;
  onBook?: (offer: HotelOffer) => void;
}

export default function HotelCard({ offer, recommended, booked, onBook }: Props) {
  return (
    <div className={`offer-card hotel-card ${recommended ? "offer-recommended" : ""}`}>
      {recommended && <span className="ribbon">Agent's pick</span>}
      <div className="hotel-main">
        <div className="hotel-info">
          <div className="hotel-title">
            <span className="strong">{offer.name}</span>
            <span className="stars" aria-label={`${offer.stars} stars`}>{"★".repeat(offer.stars)}</span>
          </div>
          <div className="muted small">
            {offer.neighborhood}, {offer.city} &middot; {offer.address}
          </div>
          <div className="small">{offer.description}</div>
          <div className="amenities">
            {offer.amenities.slice(0, 6).map((a) => (
              <span key={a} className="tag">{a}</span>
            ))}
          </div>
        </div>
        <div className="price-block">
          <div className="rating">
            <span className="score">{offer.rating.toFixed(1)}</span>
            <span className="muted small">{offer.review_count.toLocaleString()} reviews</span>
          </div>
          <div className="price">{money(offer.total_price, offer.currency)}</div>
          <div className="muted small">
            {offer.nights} night{offer.nights > 1 ? "s" : ""} &middot; {money(offer.nightly_rate, offer.currency)}/night
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
        <span>
          {offer.rooms} x {offer.room_name} ({offer.bed})
        </span>
        {offer.breakfast_included && <span className="ok-text">Breakfast included</span>}
        <span className={offer.free_cancellation ? "ok-text" : ""}>{offer.free_cancellation ? "Free cancellation" : "Non-refundable"}</span>
        {offer.rooms_left !== null && offer.rooms_left < 5 && <span className="warn-text">Only {offer.rooms_left} left</span>}
      </div>
    </div>
  );
}
