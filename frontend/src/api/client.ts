import type {
  Booking,
  ChatMessage,
  ChatResponse,
  FlightOffer,
  Health,
  HotelOffer,
  Location,
  TravelerInput,
  Trip,
  TripEvent,
  TripRequest,
  TripSummary,
  User,
} from "../types";

const BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, "") ?? "";
const USER_KEY = "atp.userEmail";

export function getUserEmail(): string | null {
  return localStorage.getItem(USER_KEY);
}

export function setUserEmail(email: string | null): void {
  if (email) localStorage.setItem(USER_KEY, email);
  else localStorage.removeItem(USER_KEY);
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

export function errorMessage(body: unknown, fallback: string): string {
  if (body && typeof body === "object" && "detail" in body) {
    const detail = (body as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      return detail
        .map((d) => {
          const item = d as { msg?: string; loc?: unknown[] };
          const field = Array.isArray(item.loc) ? item.loc.filter((p) => p !== "body").join(".") : "";
          return field ? `${field}: ${item.msg}` : item.msg;
        })
        .join("; ");
    }
  }
  return fallback;
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body) headers.set("Content-Type", "application/json");
  const email = getUserEmail();
  if (email) headers.set("X-User-Email", email);
  const res = await fetch(`${BASE}${path}`, { ...init, headers });
  if (res.status === 204) return undefined as T;
  const body = await res.json().catch(() => null);
  if (!res.ok) throw new ApiError(res.status, errorMessage(body, `${res.status} ${res.statusText}`));
  return body as T;
}

function qs(params: Record<string, string | number | undefined | null>): string {
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== null && v !== "") q.set(k, String(v));
  return q.toString();
}

export const api = {
  health: () => request<Health>("/api/health"),
  me: () => request<User>("/api/me"),
  updateMe: (name: string) => request<User>("/api/me", { method: "PUT", body: JSON.stringify({ name }) }),
  locations: (q?: string) => request<Location[]>(`/api/locations?${qs({ q })}`),

  searchFlights: (p: { origin: string; destination: string; departure_date: string; adults: number; children: number; cabin_class: string }) =>
    request<FlightOffer[]>(`/api/flights/search?${qs(p)}`),
  flightOffer: (id: string) => request<FlightOffer>(`/api/flights/offers/${encodeURIComponent(id)}`),
  searchHotels: (p: { city: string; check_in: string; check_out: string; guests: number; rooms: number; min_stars?: number }) =>
    request<HotelOffer[]>(`/api/hotels/search?${qs(p)}`),
  hotelOffer: (id: string) => request<HotelOffer>(`/api/hotels/offers/${encodeURIComponent(id)}`),

  createTrip: (body: TripRequest) => request<Trip>("/api/trips", { method: "POST", body: JSON.stringify(body) }),
  trips: () => request<TripSummary[]>("/api/trips"),
  trip: (id: number) => request<Trip>(`/api/trips/${id}`),
  deleteTrip: (id: number) => request<void>(`/api/trips/${id}`, { method: "DELETE" }),
  replan: (id: number) => request<Trip>(`/api/trips/${id}/replan`, { method: "POST" }),
  events: (id: number, after = 0) => request<TripEvent[]>(`/api/trips/${id}/events?after=${after}`),
  streamUrl: (id: number, after = 0) => {
    const email = getUserEmail();
    return `${BASE}/api/trips/${id}/stream?${qs({ after, user: email })}`;
  },
  messages: (id: number) => request<ChatMessage[]>(`/api/trips/${id}/messages`),
  sendMessage: (id: number, message: string) =>
    request<ChatResponse>(`/api/trips/${id}/messages`, { method: "POST", body: JSON.stringify({ message }) }),

  bookings: (params: { status?: string; trip_id?: number } = {}) => request<Booking[]>(`/api/bookings?${qs(params)}`),
  book: (body: { offer_id: string; trip_id?: number | null; contact_email: string; contact_phone?: string; travelers: TravelerInput[] }) =>
    request<Booking>("/api/bookings", { method: "POST", body: JSON.stringify(body) }),
  cancelBooking: (reference: string) => request<Booking>(`/api/bookings/${reference}/cancel`, { method: "POST" }),
};
