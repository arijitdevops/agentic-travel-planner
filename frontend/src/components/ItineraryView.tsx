import { useState } from "react";
import { money, shortDate } from "../lib/format";
import type { Itinerary } from "../types";

const CATEGORY_ICON: Record<string, string> = {
  food: "\u{1F37D}",
  sightseeing: "\u{1F4F7}",
  culture: "\u{1F3DB}",
  nature: "\u{1F333}",
  shopping: "\u{1F6CD}",
  nightlife: "\u{1F378}",
  transport: "\u{2708}",
  rest: "\u{2615}",
};

export default function ItineraryView({ itinerary }: { itinerary: Itinerary }) {
  const [open, setOpen] = useState<number | null>(null);
  return (
    <div>
      <div className="card">
        <h2>{itinerary.title}</h2>
        <p>{itinerary.overview}</p>
        {itinerary.packing_list.length > 0 && (
          <div className="small">
            <span className="strong">Pack: </span>
            {itinerary.packing_list.join(" · ")}
          </div>
        )}
      </div>
      <div className="day-list">
        {itinerary.days.map((d) => {
          const cost = d.activities.reduce((s, a) => s + (a.estimated_cost || 0), 0);
          const collapsed = open !== null && open !== d.day;
          return (
            <section key={d.day} className="day-card card">
              <header className="day-head" onClick={() => setOpen(open === d.day ? null : d.day)}>
                <div className="day-num">Day {d.day}</div>
                <div className="day-title">
                  <div className="strong">{d.theme}</div>
                  <div className="muted small">
                    {shortDate(d.date)} &middot; {d.city}
                  </div>
                </div>
                <div className="muted small">{cost > 0 ? `~${money(cost)} pp` : "Free day"}</div>
              </header>
              {!collapsed && (
                <ol className="timeline">
                  {d.activities.map((a, i) => (
                    <li key={i}>
                      <span className="tl-time">{a.time}</span>
                      <span className="tl-icon" aria-hidden>{CATEGORY_ICON[a.category] ?? "•"}</span>
                      <div className="tl-body">
                        <div className="strong">{a.title}</div>
                        {a.description && <div className="small">{a.description}</div>}
                        <div className="muted small">
                          {a.location}
                          {a.estimated_cost > 0 && ` · ~${money(a.estimated_cost)} pp`}
                        </div>
                      </div>
                    </li>
                  ))}
                </ol>
              )}
              {!collapsed && d.notes && <p className="day-notes small">{d.notes}</p>}
            </section>
          );
        })}
      </div>
    </div>
  );
}
