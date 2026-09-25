import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../api/client";
import AgentProgress from "../components/AgentProgress";
import BookingDialog, { type BookableOffer } from "../components/BookingDialog";
import BudgetView from "../components/BudgetView";
import ChatPanel from "../components/ChatPanel";
import FlightCard from "../components/FlightCard";
import HotelCard from "../components/HotelCard";
import InsightsView from "../components/InsightsView";
import ItineraryView from "../components/ItineraryView";
import StatusBadge from "../components/StatusBadge";
import { dateRange, money, shortDate } from "../lib/format";
import type { Booking, Trip } from "../types";

type Tab = "itinerary" | "flights" | "hotels" | "budget" | "insights";

export default function TripPage() {
  const { tripId } = useParams();
  const id = Number(tripId);
  const navigate = useNavigate();
  const [trip, setTrip] = useState<Trip | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("itinerary");
  const [booking, setBooking] = useState<BookableOffer | null>(null);
  const [bookings, setBookings] = useState<Booking[]>([]);

  const load = useCallback(() => {
    api.trip(id).then(setTrip).catch((e: Error) => setError(e.message));
    api.bookings({ trip_id: id, status: "confirmed" }).then(setBookings).catch(() => undefined);
  }, [id]);

  useEffect(load, [load]);
  useEffect(() => {
    if (trip && trip.status === "failed") setTab("flights");
  }, [trip?.status]);

  if (error) return <div className="alert alert-error">{error}</div>;
  if (!trip) return <div className="loading">Loading trip...</div>;

  const plan = trip.plan;
  const inProgress = trip.status === "queued" || trip.status === "running";
  const bookedIds = new Set(bookings.map((b) => b.offer_id));
  const flightPick = (leg: number) => plan?.flights?.choices.find((c) => c.leg_index === leg);
  const hotelPick = (stay: number) => plan?.hotels?.choices.find((c) => c.stay_index === stay);
  const tabs: [Tab, string][] = plan?.itinerary
    ? [["itinerary", "Itinerary"], ["flights", "Flights"], ["hotels", "Hotels"], ["budget", "Budget"], ["insights", "Insights"]]
    : [["flights", "Flights"], ["hotels", "Hotels"]];

  async function remove() {
    if (!confirm("Delete this trip? Bookings are kept.")) return;
    await api.deleteTrip(id);
    navigate("/trips");
  }

  async function replan() {
    setTrip(await api.replan(id));
  }

  return (
    <div className="trip-page">
      <div className="trip-header">
        <div>
          <div className="row">
            <h1>{trip.title}</h1>
            <StatusBadge status={trip.status} />
          </div>
          <p className="muted">
            {dateRange(trip.start_date, trip.end_date)} &middot; {trip.adults} adult{trip.adults > 1 ? "s" : ""}
            {trip.children > 0 && `, ${trip.children} child${trip.children > 1 ? "ren" : ""}`} &middot; budget {money(trip.budget, trip.currency)} &middot;{" "}
            {trip.travel_style}, {trip.pace} pace
            {trip.interests.length > 0 && ` · ${trip.interests.join(", ")}`}
          </p>
        </div>
        {!inProgress && (
          <div className="row">
            <button className="btn" onClick={replan}>Re-plan</button>
            <button className="btn btn-danger-ghost" onClick={remove}>Delete</button>
          </div>
        )}
      </div>

      {inProgress && <AgentProgress tripId={trip.id} onFinished={load} />}

      {trip.status === "failed" && (
        <div className="alert alert-error">
          <strong>The agents could not finish this plan.</strong> {trip.error}
          {plan && plan.flight_options.length > 0 && <div className="small mt">You can still book any of the flight and hotel options found below.</div>}
        </div>
      )}

      {!inProgress && plan && (
        <div className={trip.status === "completed" ? "trip-layout" : ""}>
          <div className="trip-main">
            <div className="tabs" role="tablist">
              {tabs.map(([key, label]) => (
                <button key={key} role="tab" aria-selected={tab === key} className={tab === key ? "active" : ""} onClick={() => setTab(key)}>
                  {label}
                </button>
              ))}
            </div>

            {tab === "itinerary" && plan.itinerary && <ItineraryView itinerary={plan.itinerary} />}

            {tab === "flights" && (
              <div>
                {plan.flights?.summary && <p className="agent-note">{plan.flights.summary}</p>}
                {plan.legs.map((leg, i) => {
                  const pick = flightPick(i);
                  const options = [...(plan.flight_options[i] ?? [])].sort(
                    (a, b) => Number(b.id === pick?.offer_id) - Number(a.id === pick?.offer_id),
                  );
                  return (
                    <section key={leg.index} className="leg-section">
                      <h3>
                        {leg.origin_city} to {leg.destination_city} <span className="muted small">{shortDate(leg.date)}</span>
                      </h3>
                      {pick?.reasoning && <p className="agent-note small">{pick.reasoning}</p>}
                      {options.length === 0 && <p className="muted">No flights found for this leg.</p>}
                      {options.map((o) => (
                        <FlightCard key={o.id} offer={o} recommended={o.id === pick?.offer_id} booked={bookedIds.has(o.id)}
                          onBook={(offer) => setBooking({ kind: "flight", offer })} />
                      ))}
                    </section>
                  );
                })}
              </div>
            )}

            {tab === "hotels" && (
              <div>
                {plan.hotels?.summary && <p className="agent-note">{plan.hotels.summary}</p>}
                {plan.stays.map((stay, i) => {
                  const pick = hotelPick(i);
                  const options = [...(plan.hotel_options[i] ?? [])].sort(
                    (a, b) => Number(b.id === pick?.offer_id) - Number(a.id === pick?.offer_id),
                  );
                  return (
                    <section key={stay.index} className="leg-section">
                      <h3>
                        {stay.city} <span className="muted small">{dateRange(stay.check_in, stay.check_out)} &middot; {stay.nights} nights</span>
                      </h3>
                      {pick?.reasoning && <p className="agent-note small">{pick.reasoning}</p>}
                      {options.length === 0 && <p className="muted">No hotels matched.</p>}
                      {options.map((o) => (
                        <HotelCard key={o.id} offer={o} recommended={o.id === pick?.offer_id} booked={bookedIds.has(o.id)}
                          onBook={(offer) => setBooking({ kind: "hotel", offer })} />
                      ))}
                    </section>
                  );
                })}
              </div>
            )}

            {tab === "budget" && plan.budget && <BudgetView budget={plan.budget} />}
            {tab === "insights" && <InsightsView plan={plan} />}
          </div>
          {trip.status === "completed" && <ChatPanel trip={trip} onTripUpdated={setTrip} />}
        </div>
      )}

      {booking && (
        <BookingDialog
          item={booking}
          tripId={trip.id}
          onClose={() => setBooking(null)}
          onBooked={(b) => setBookings((prev) => [...prev, b])}
        />
      )}
    </div>
  );
}
