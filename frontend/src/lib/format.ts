export function money(amount: number, currency = "USD", digits = 0): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(amount);
}

export function duration(minutes: number): string {
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return h ? `${h}h ${String(m).padStart(2, "0")}m` : `${m}m`;
}

/** "2026-10-01T09:05:00" -> "09:05" (times are already local to the airport). */
export function clock(iso: string): string {
  return iso.slice(11, 16);
}

export function shortDate(iso: string): string {
  const [y, m, d] = iso.slice(0, 10).split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, d)).toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short", timeZone: "UTC" });
}

export function dateRange(start: string, end: string): string {
  return `${shortDate(start)} - ${shortDate(end)}`;
}

export function nightsBetween(start: string, end: string): number {
  return Math.round((Date.parse(end) - Date.parse(start)) / 86_400_000);
}

/** Days after the arrival date shown as "+1". */
export function dayOffset(departure: string, arrival: string): number {
  return Math.round((Date.parse(arrival.slice(0, 10)) - Date.parse(departure.slice(0, 10))) / 86_400_000);
}

export function addDays(iso: string, days: number): string {
  const d = new Date(`${iso.slice(0, 10)}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString().slice(0, 10);
}

export function cabinLabel(cabin: string): string {
  return cabin.replace("_", " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export function stopsLabel(stops: number, via: string | null): string {
  return stops === 0 ? "Nonstop" : `${stops} stop${stops > 1 ? "s" : ""}${via ? ` via ${via}` : ""}`;
}

/** Split N nights across D destinations the same way the backend does. */
export function splitNights(total: number, destinations: number): number[] {
  const base = Math.floor(total / destinations);
  const extra = total % destinations;
  return Array.from({ length: destinations }, (_, i) => base + (i < extra ? 1 : 0));
}
