import type { Location } from "../types";

interface Props {
  id?: string;
  value: string;
  onChange: (iata: string) => void;
  locations: Location[];
  exclude?: string[];
  placeholder?: string;
  required?: boolean;
}

export default function LocationSelect({ id, value, onChange, locations, exclude = [], placeholder = "Select a city", required }: Props) {
  const byRegion = new Map<string, Location[]>();
  for (const loc of locations) {
    if (exclude.includes(loc.iata) && loc.iata !== value) continue;
    byRegion.set(loc.region, [...(byRegion.get(loc.region) ?? []), loc]);
  }
  return (
    <select id={id} value={value} onChange={(e) => onChange(e.target.value)} required={required}>
      <option value="">{placeholder}</option>
      {[...byRegion.entries()]
        .sort(([a], [b]) => a.localeCompare(b))
        .map(([region, locs]) => (
          <optgroup key={region} label={region}>
            {locs.map((l) => (
              <option key={l.iata} value={l.iata}>
                {l.city}, {l.country} ({l.iata})
              </option>
            ))}
          </optgroup>
        ))}
    </select>
  );
}
