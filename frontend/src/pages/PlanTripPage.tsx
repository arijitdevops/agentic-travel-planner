import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import LocationSelect from "../components/LocationSelect";
import { addDays, money, nightsBetween, splitNights } from "../lib/format";
import type { Cabin, Location, Pace, TravelStyle, TripRequest } from "../types";

const INTERESTS = [
  "culture", "history", "food", "nightlife", "nature", "beaches", "adventure",
  "shopping", "art", "museums", "architecture", "photography", "wellness", "family", "sports",
];

const today = new Date().toISOString().slice(0, 10);

export default function PlanTripPage() {
  const navigate = useNavigate();
  const [locations, setLocations] = useState<Location[]>([]);
  const [form, setForm] = useState<TripRequest>({
    origin: "",
    destinations: [""],
    start_date: addDays(today, 30),
    end_date: addDays(today, 36),
    adults: 2,
    children: 0,
    budget: 5000,
    cabin_class: "economy",
    hotel_min_stars: 3,
    pace: "balanced",
    travel_style: "comfort",
    interests: ["food", "culture"],
    dietary_needs: "",
    accessibility_needs: "",
    notes: "",
  });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.locations().then(setLocations).catch((e: Error) => setError(e.message));
  }, []);

  const set = <K extends keyof TripRequest>(key: K, value: TripRequest[K]) => setForm((f) => ({ ...f, [key]: value }));
  const nights = nightsBetween(form.start_date, form.end_date);
  const destinations = form.destinations.filter(Boolean);
  const split = useMemo(() => (destinations.length && nights > 0 ? splitNights(nights, destinations.length) : []), [nights, destinations.length]);
  const cityName = (iata: string) => locations.find((l) => l.iata === iata)?.city ?? iata;
  const travelers = form.adults + form.children;

  function updateDestination(i: number, iata: string) {
    set("destinations", form.destinations.map((d, idx) => (idx === i ? iata : d)));
  }

  function toggleInterest(tag: string) {
    set("interests", form.interests.includes(tag) ? form.interests.filter((t) => t !== tag) : [...form.interests, tag]);
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (!destinations.length) return setError("Choose at least one destination.");
    if (nights < destinations.length) return setError("You need at least one night per destination.");
    setSubmitting(true);
    try {
      const trip = await api.createTrip({
        ...form,
        destinations,
        dietary_needs: form.dietary_needs || null,
        accessibility_needs: form.accessibility_needs || null,
        notes: form.notes || null,
      });
      navigate(`/trips/${trip.id}`);
    } catch (err) {
      setError((err as Error).message);
      setSubmitting(false);
    }
  }

  return (
    <div className="plan-page">
      <section className="hero">
        <h1>Plan your next trip with a team of AI travel agents</h1>
        <p>
          Six specialist agents profile your preferences, research destinations, pick flights and hotels from live inventory, design a
          day-by-day itinerary and check it against your budget. Then refine it by chat and book in one click.
        </p>
      </section>

      <form className="card form-card" onSubmit={submit}>
        <div className="form-section">
          <h2>Where to?</h2>
          <div className="grid-2">
            <label>
              Flying from
              <LocationSelect value={form.origin} onChange={(v) => set("origin", v)} locations={locations} exclude={destinations} required />
            </label>
            <div>
              <span className="label-text">Destinations (visited in order)</span>
              {form.destinations.map((d, i) => (
                <div className="row" key={i}>
                  <LocationSelect
                    value={d}
                    onChange={(v) => updateDestination(i, v)}
                    locations={locations}
                    exclude={[form.origin, ...destinations]}
                    placeholder={`Destination ${i + 1}`}
                    required={i === 0}
                  />
                  {form.destinations.length > 1 && (
                    <button type="button" className="btn btn-ghost btn-icon" aria-label="Remove destination"
                      onClick={() => set("destinations", form.destinations.filter((_, idx) => idx !== i))}>
                      &times;
                    </button>
                  )}
                </div>
              ))}
              {form.destinations.length < 4 && (
                <button type="button" className="btn btn-link" onClick={() => set("destinations", [...form.destinations, ""])}>
                  + Add another city
                </button>
              )}
            </div>
          </div>
        </div>

        <div className="form-section">
          <h2>When and who</h2>
          <div className="grid-4">
            <label>
              Depart
              <input type="date" min={addDays(today, 1)} value={form.start_date} onChange={(e) => set("start_date", e.target.value)} required />
            </label>
            <label>
              Return
              <input type="date" min={addDays(form.start_date, 1)} value={form.end_date} onChange={(e) => set("end_date", e.target.value)} required />
            </label>
            <label>
              Adults
              <input type="number" min={1} max={9} value={form.adults} onChange={(e) => set("adults", Number(e.target.value))} />
            </label>
            <label>
              Children
              <input type="number" min={0} max={8} value={form.children} onChange={(e) => set("children", Number(e.target.value))} />
            </label>
          </div>
          {split.length > 0 && (
            <p className="hint">
              {nights} nights: {destinations.map((d, i) => `${cityName(d)} (${split[i]})`).join(" -> ")}
            </p>
          )}
        </div>

        <div className="form-section">
          <h2>Budget and comfort</h2>
          <div className="grid-4">
            <label>
              Total budget (USD)
              <input type="number" min={100} step={50} value={form.budget} onChange={(e) => set("budget", Number(e.target.value))} required />
              <span className="hint">{travelers > 0 && nights > 0 ? `${money(form.budget / travelers / nights)} per person per night` : ""}</span>
            </label>
            <label>
              Cabin
              <select value={form.cabin_class} onChange={(e) => set("cabin_class", e.target.value as Cabin)}>
                <option value="economy">Economy</option>
                <option value="premium_economy">Premium economy</option>
                <option value="business">Business</option>
              </select>
            </label>
            <label>
              Hotel rating
              <select value={form.hotel_min_stars} onChange={(e) => set("hotel_min_stars", Number(e.target.value))}>
                {[2, 3, 4, 5].map((s) => (
                  <option key={s} value={s}>{s}+ stars</option>
                ))}
              </select>
            </label>
            <div>
              <span className="label-text">Travel style</span>
              <Segmented options={["budget", "comfort", "luxury"]} value={form.travel_style} onChange={(v) => set("travel_style", v as TravelStyle)} />
            </div>
          </div>
        </div>

        <div className="form-section">
          <h2>What you enjoy</h2>
          <div className="chips">
            {INTERESTS.map((tag) => (
              <button type="button" key={tag} className={`chip ${form.interests.includes(tag) ? "chip-on" : ""}`} onClick={() => toggleInterest(tag)}>
                {tag}
              </button>
            ))}
          </div>
          <div className="grid-2 mt">
            <div>
              <span className="label-text">Pace</span>
              <Segmented options={["relaxed", "balanced", "packed"]} value={form.pace} onChange={(v) => set("pace", v as Pace)} />
            </div>
            <label>
              Dietary needs
              <input placeholder="e.g. vegetarian, nut allergy, halal" value={form.dietary_needs ?? ""} onChange={(e) => set("dietary_needs", e.target.value)} />
            </label>
            <label>
              Accessibility needs
              <input placeholder="e.g. step-free access, limited walking" value={form.accessibility_needs ?? ""} onChange={(e) => set("accessibility_needs", e.target.value)} />
            </label>
            <label>
              Anything else?
              <input placeholder="e.g. anniversary trip, love jazz bars, hate early flights" value={form.notes ?? ""} onChange={(e) => set("notes", e.target.value)} />
            </label>
          </div>
        </div>

        {error && <div className="alert alert-error">{error}</div>}
        <div className="form-actions">
          <button className="btn btn-primary btn-large" disabled={submitting}>
            {submitting ? "Starting your agents..." : "Plan my trip"}
          </button>
        </div>
      </form>
    </div>
  );
}

function Segmented({ options, value, onChange }: { options: string[]; value: string; onChange: (v: string) => void }) {
  return (
    <div className="segmented" role="radiogroup">
      {options.map((o) => (
        <button type="button" role="radio" aria-checked={o === value} key={o} className={o === value ? "on" : ""} onClick={() => onChange(o)}>
          {o}
        </button>
      ))}
    </div>
  );
}
