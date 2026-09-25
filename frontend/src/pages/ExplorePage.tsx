import { useEffect, useState } from "react";
import { api } from "../api/client";
import BookingDialog, { type BookableOffer } from "../components/BookingDialog";
import FlightCard from "../components/FlightCard";
import HotelCard from "../components/HotelCard";
import LocationSelect from "../components/LocationSelect";
import { addDays } from "../lib/format";
import type { Cabin, FlightOffer, HotelOffer, Location } from "../types";

const today = new Date().toISOString().slice(0, 10);

export default function ExplorePage() {
  const [mode, setMode] = useState<"flights" | "hotels">("flights");
  const [locations, setLocations] = useState<Location[]>([]);
  const [origin, setOrigin] = useState("");
  const [destination, setDestination] = useState("");
  const [date, setDate] = useState(addDays(today, 21));
  const [checkOut, setCheckOut] = useState(addDays(today, 24));
  const [adults, setAdults] = useState(1);
  const [children, setChildren] = useState(0);
  const [cabin, setCabin] = useState<Cabin>("economy");
  const [minStars, setMinStars] = useState(3);
  const [flights, setFlights] = useState<FlightOffer[] | null>(null);
  const [hotels, setHotels] = useState<HotelOffer[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [booking, setBooking] = useState<BookableOffer | null>(null);

  useEffect(() => {
    api.locations().then(setLocations).catch((e: Error) => setError(e.message));
  }, []);

  async function search(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      if (mode === "flights") {
        setFlights(await api.searchFlights({ origin, destination, departure_date: date, adults, children, cabin_class: cabin }));
      } else {
        const guests = adults + children;
        setHotels(await api.searchHotels({ city: destination, check_in: date, check_out: checkOut, guests, rooms: Math.max(1, Math.ceil(guests / 4)), min_stars: minStars }));
      }
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <div className="page-head">
        <h1>Flights and hotels</h1>
        <div className="segmented">
          <button className={mode === "flights" ? "on" : ""} onClick={() => setMode("flights")}>Flights</button>
          <button className={mode === "hotels" ? "on" : ""} onClick={() => setMode("hotels")}>Hotels</button>
        </div>
      </div>
      <form className="card search-bar" onSubmit={search}>
        {mode === "flights" && (
          <label>
            From
            <LocationSelect value={origin} onChange={setOrigin} locations={locations} exclude={[destination]} required />
          </label>
        )}
        <label>
          {mode === "flights" ? "To" : "City"}
          <LocationSelect value={destination} onChange={setDestination} locations={locations} exclude={[origin]} required />
        </label>
        <label>
          {mode === "flights" ? "Date" : "Check-in"}
          <input type="date" min={today} value={date} onChange={(e) => setDate(e.target.value)} required />
        </label>
        {mode === "hotels" && (
          <label>
            Check-out
            <input type="date" min={addDays(date, 1)} value={checkOut} onChange={(e) => setCheckOut(e.target.value)} required />
          </label>
        )}
        <label>
          Adults
          <input type="number" min={1} max={9} value={adults} onChange={(e) => setAdults(Number(e.target.value))} />
        </label>
        <label>
          Children
          <input type="number" min={0} max={8} value={children} onChange={(e) => setChildren(Number(e.target.value))} />
        </label>
        {mode === "flights" ? (
          <label>
            Cabin
            <select value={cabin} onChange={(e) => setCabin(e.target.value as Cabin)}>
              <option value="economy">Economy</option>
              <option value="premium_economy">Premium economy</option>
              <option value="business">Business</option>
            </select>
          </label>
        ) : (
          <label>
            Stars
            <select value={minStars} onChange={(e) => setMinStars(Number(e.target.value))}>
              {[2, 3, 4, 5].map((s) => (
                <option key={s} value={s}>{s}+</option>
              ))}
            </select>
          </label>
        )}
        <button className="btn btn-primary" disabled={loading}>{loading ? "Searching..." : "Search"}</button>
      </form>
      {error && <div className="alert alert-error">{error}</div>}
      {mode === "flights" && flights && (
        <div>
          {flights.length === 0 && <p className="muted">No flights on that date - try another day.</p>}
          {flights.map((o) => (
            <FlightCard key={o.id} offer={o} onBook={(offer) => setBooking({ kind: "flight", offer })} />
          ))}
        </div>
      )}
      {mode === "hotels" && hotels && (
        <div>
          {hotels.length === 0 && <p className="muted">No hotels matched.</p>}
          {hotels.map((o) => (
            <HotelCard key={o.id} offer={o} onBook={(offer) => setBooking({ kind: "hotel", offer })} />
          ))}
        </div>
      )}
      {booking && <BookingDialog item={booking} onClose={() => setBooking(null)} />}
    </div>
  );
}
