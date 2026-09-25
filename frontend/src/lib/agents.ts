// Mirrors backend/app/agents/config/agents.yaml (planning crew order).
export const PLANNING_AGENTS = [
  { role: "Traveler Profile Analyst", blurb: "Understands your preferences, constraints and pace" },
  { role: "Destination Research Specialist", blurb: "Researches areas, experiences, weather and local tips" },
  { role: "Flight Booking Specialist", blurb: "Compares bookable flights for every leg" },
  { role: "Accommodation Specialist", blurb: "Shortlists hotels in the right neighbourhoods" },
  { role: "Itinerary Architect", blurb: "Designs the day-by-day plan" },
  { role: "Travel Budget Analyst", blurb: "Checks everything against your budget" },
] as const;
