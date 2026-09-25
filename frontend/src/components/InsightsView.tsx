import { money } from "../lib/format";
import type { Plan } from "../types";

export default function InsightsView({ plan }: { plan: Plan }) {
  const profile = plan.profile;
  const research = plan.research;
  return (
    <div className="insights">
      {profile && (
        <div className="card">
          <h2>Your traveler profile</h2>
          <p>{profile.summary}</p>
          <div className="grid-2">
            <List title="Priorities" items={profile.priorities} />
            <List title="Must-haves" items={profile.must_haves} />
            <List title="Avoid" items={profile.things_to_avoid} />
            <div>
              <h4>Daily rhythm</h4>
              <p className="small">{profile.daily_rhythm}</p>
            </div>
          </div>
        </div>
      )}
      {research?.destinations.map((d) => (
        <div className="card" key={d.city}>
          <h2>{d.city}</h2>
          <p>{d.overview}</p>
          <div className="grid-2">
            <div>
              <h4>Top experiences</h4>
              <ul className="experiences">
                {d.top_experiences.map((e) => (
                  <li key={e.name}>
                    <span className="strong">{e.name}</span>
                    <span className="tag">{e.interest}</span>
                    {e.estimated_cost_per_person > 0 && <span className="muted small"> ~{money(e.estimated_cost_per_person)} pp</span>}
                    <div className="small">{e.description}</div>
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <List title="Where to stay" items={d.best_areas_to_stay} />
              <List title="Food and drink" items={d.food_and_drink} />
              <List title="Local tips" items={d.local_tips} />
              {d.weather_and_packing && (
                <>
                  <h4>Weather and packing</h4>
                  <p className="small">{d.weather_and_packing}</p>
                </>
              )}
              {d.entry_and_safety_notes && (
                <>
                  <h4>Entry and safety</h4>
                  <p className="small">{d.entry_and_safety_notes}</p>
                </>
              )}
            </div>
          </div>
        </div>
      ))}
      {research && research.sources.length > 0 && (
        <div className="card small">
          <h4>Sources consulted by the research agent</h4>
          <ul>
            {research.sources.map((s) => (
              <li key={s}>
                <a href={s} target="_blank" rel="noreferrer">{s}</a>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function List({ title, items }: { title: string; items: string[] }) {
  if (!items.length) return null;
  return (
    <div>
      <h4>{title}</h4>
      <ul className="small">
        {items.map((i) => (
          <li key={i}>{i}</li>
        ))}
      </ul>
    </div>
  );
}
