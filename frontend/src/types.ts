// Shapes returned by the FastAPI backend (see backend/app/schemas.py and app/agents/schemas.py).

export type Cabin = "economy" | "premium_economy" | "business";
export type Pace = "relaxed" | "balanced" | "packed";
export type TravelStyle = "budget" | "comfort" | "luxury";
export type TripStatus = "queued" | "running" | "completed" | "failed";

export interface User {
  id: number;
  email: string;
  name: string;
}

export interface Health {
  status: string;
  version: string;
  llm_configured: boolean;
  llm_model: string;
  flight_provider: string;
  hotel_provider: string;
  web_search: string;
  database: string;
}

export interface Location {
  iata: string;
  city: string;
  airport: string;
  country: string;
  region: string;
  has_hotels: boolean;
}

export interface FlightSegment {
  flight_number: string;
  airline_code: string;
  airline_name: string;
  origin: string;
  destination: string;
  departure: string;
  arrival: string;
  duration_minutes: number;
  aircraft: string | null;
}

export interface FlightOffer {
  id: string;
  provider: string;
  origin: string;
  origin_city: string;
  destination: string;
  destination_city: string;
  departure_date: string;
  departure: string;
  arrival: string;
  duration_minutes: number;
  stops: number;
  via: string | null;
  airline_code: string;
  airline_name: string;
  flight_number: string;
  aircraft: string | null;
  cabin_class: Cabin;
  adults: number;
  children: number;
  price_per_adult: number;
  total_price: number;
  currency: string;
  seats_left: number | null;
  baggage: string;
  refundable: boolean;
  segments: FlightSegment[];
}

export interface HotelOffer {
  id: string;
  provider: string;
  hotel_code: string;
  name: string;
  city_code: string;
  city: string;
  neighborhood: string;
  address: string;
  stars: number;
  rating: number;
  review_count: number;
  amenities: string[];
  description: string;
  room_type: string;
  room_name: string;
  bed: string;
  check_in: string;
  check_out: string;
  nights: number;
  rooms: number;
  guests: number;
  nightly_rate: number;
  total_price: number;
  currency: string;
  rooms_left: number | null;
  free_cancellation: boolean;
  breakfast_included: boolean;
}

export interface TripRequest {
  origin: string;
  destinations: string[];
  start_date: string;
  end_date: string;
  adults: number;
  children: number;
  budget: number;
  cabin_class: Cabin;
  hotel_min_stars: number;
  pace: Pace;
  travel_style: TravelStyle;
  interests: string[];
  dietary_needs?: string | null;
  accessibility_needs?: string | null;
  notes?: string | null;
  title?: string | null;
}

export interface Leg {
  index: number;
  origin: string;
  destination: string;
  date: string;
  origin_city: string;
  destination_city: string;
}

export interface Stay {
  index: number;
  city_code: string;
  city: string;
  check_in: string;
  check_out: string;
  nights: number;
}

export interface TravelerProfile {
  summary: string;
  priorities: string[];
  must_haves: string[];
  things_to_avoid: string[];
  accommodation_preferences: string;
  flight_preferences: string;
  daily_rhythm: string;
}

export interface Experience {
  name: string;
  description: string;
  interest: string;
  estimated_cost_per_person: number;
}

export interface DestinationInsight {
  city: string;
  overview: string;
  best_areas_to_stay: string[];
  top_experiences: Experience[];
  food_and_drink: string[];
  local_tips: string[];
  weather_and_packing: string;
  entry_and_safety_notes: string;
}

export interface Activity {
  time: string;
  title: string;
  description: string;
  category: string;
  location: string;
  estimated_cost: number;
}

export interface DayPlan {
  day: number;
  date: string;
  city: string;
  theme: string;
  activities: Activity[];
  notes: string;
}

export interface Itinerary {
  title: string;
  overview: string;
  days: DayPlan[];
  packing_list: string[];
}

export interface BudgetLine {
  category: string;
  amount: number;
  notes: string;
}

export interface Budget {
  currency: string;
  lines: BudgetLine[];
  total: number;
  budget: number;
  within_budget: boolean;
  savings_tips: string[];
  summary: string;
}

export interface FlightChoice {
  leg_index: number;
  offer_id: string | null;
  alternative_offer_ids: string[];
  reasoning: string;
}

export interface HotelChoice {
  stay_index: number;
  offer_id: string | null;
  alternative_offer_ids: string[];
  reasoning: string;
}

export interface Plan {
  legs: Leg[];
  stays: Stay[];
  flight_options: FlightOffer[][];
  hotel_options: HotelOffer[][];
  profile?: TravelerProfile;
  research?: { destinations: DestinationInsight[]; sources: string[] };
  flights?: { summary: string; choices: FlightChoice[] };
  hotels?: { summary: string; choices: HotelChoice[] };
  itinerary?: Itinerary;
  budget?: Budget;
  generated_at?: string;
  model?: string;
}

export interface TripSummary {
  id: number;
  title: string;
  origin: string;
  destinations: string[];
  start_date: string;
  end_date: string;
  adults: number;
  children: number;
  budget: number;
  currency: string;
  status: TripStatus;
  current_step: string | null;
  created_at: string;
  completed_at: string | null;
}

export interface Trip extends TripSummary {
  cabin_class: Cabin;
  hotel_min_stars: number;
  pace: Pace;
  travel_style: TravelStyle;
  interests: string[];
  dietary_needs: string | null;
  accessibility_needs: string | null;
  notes: string | null;
  error: string | null;
  plan: Plan | null;
  plan_version: number;
}

export interface TripEvent {
  seq: number;
  agent: string | null;
  kind: "info" | "agent_started" | "agent_completed" | "tool" | "error" | "done";
  message: string;
  created_at: string;
}

export interface ChatMessage {
  id: number;
  role: "user" | "assistant";
  content: string;
  changes: string[];
  created_at: string;
}

export interface ChatResponse {
  user_message: ChatMessage;
  assistant_message: ChatMessage;
  trip: Trip;
}

export interface TravelerInput {
  first_name: string;
  last_name: string;
  traveler_type: "adult" | "child";
  date_of_birth?: string | null;
}

export interface Booking {
  id: number;
  reference: string;
  kind: "flight" | "hotel";
  provider: string;
  status: "confirmed" | "cancelled";
  offer_id: string;
  trip_id: number | null;
  summary: string;
  details: FlightOffer | HotelOffer;
  total_price: number;
  currency: string;
  refund_amount: number | null;
  contact_email: string;
  contact_phone: string | null;
  created_at: string;
  cancelled_at: string | null;
  travelers: (TravelerInput & { ticket_number: string | null })[];
  simulated: boolean;
}
