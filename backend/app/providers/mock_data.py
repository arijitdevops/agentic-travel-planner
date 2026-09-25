"""Deterministic mock travel inventory.

Real airports and neighbourhoods, **fictional** carriers, hotels, schedules and
fares. Everything is generated from fixed seeds so that every install produces
exactly the same inventory (useful for demos and tests).
"""

from __future__ import annotations

import hashlib
import math
import random
from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True)
class City:
    iata: str
    airport: str
    city: str
    country: str
    country_code: str
    region: str
    lat: float
    lon: float
    timezone: str
    currency: str
    language: str
    cost_index: float  # 1.0 ~ mid-priced western city
    neighborhoods: tuple[str, ...] = field(default_factory=tuple)


CITIES: list[City] = [
    City("LHR", "Heathrow Airport", "London", "United Kingdom", "GB", "Europe", 51.47, -0.4543, "Europe/London", "GBP", "English", 1.35, ("Covent Garden", "South Kensington", "Shoreditch", "Southbank")),
    City("CDG", "Charles de Gaulle Airport", "Paris", "France", "FR", "Europe", 49.0097, 2.5479, "Europe/Paris", "EUR", "French", 1.3, ("Le Marais", "Saint-Germain-des-Pres", "Montmartre", "Latin Quarter")),
    City("FCO", "Leonardo da Vinci-Fiumicino Airport", "Rome", "Italy", "IT", "Europe", 41.8003, 12.2389, "Europe/Rome", "EUR", "Italian", 1.1, ("Centro Storico", "Trastevere", "Monti", "Prati")),
    City("BCN", "Josep Tarradellas Barcelona-El Prat Airport", "Barcelona", "Spain", "ES", "Europe", 41.2974, 2.0833, "Europe/Madrid", "EUR", "Spanish, Catalan", 1.05, ("Gothic Quarter", "Eixample", "El Born", "Gracia")),
    City("AMS", "Amsterdam Airport Schiphol", "Amsterdam", "Netherlands", "NL", "Europe", 52.3105, 4.7683, "Europe/Amsterdam", "EUR", "Dutch", 1.3, ("Jordaan", "De Pijp", "Canal Ring", "Museum Quarter")),
    City("BER", "Berlin Brandenburg Airport", "Berlin", "Germany", "DE", "Europe", 52.3667, 13.5033, "Europe/Berlin", "EUR", "German", 1.0, ("Mitte", "Kreuzberg", "Prenzlauer Berg", "Charlottenburg")),
    City("LIS", "Humberto Delgado Airport", "Lisbon", "Portugal", "PT", "Europe", 38.7813, -9.1359, "Europe/Lisbon", "EUR", "Portuguese", 0.9, ("Alfama", "Baixa", "Bairro Alto", "Belem")),
    City("PRG", "Vaclav Havel Airport Prague", "Prague", "Czechia", "CZ", "Europe", 50.1008, 14.26, "Europe/Prague", "CZK", "Czech", 0.8, ("Old Town", "Mala Strana", "Vinohrady", "New Town")),
    City("ATH", "Athens International Airport", "Athens", "Greece", "GR", "Europe", 37.9364, 23.9445, "Europe/Athens", "EUR", "Greek", 0.85, ("Plaka", "Monastiraki", "Koukaki", "Kolonaki")),
    City("ZRH", "Zurich Airport", "Zurich", "Switzerland", "CH", "Europe", 47.4582, 8.5555, "Europe/Zurich", "CHF", "German", 1.6, ("Altstadt", "Zurich West", "Seefeld", "Enge")),
    City("KEF", "Keflavik International Airport", "Reykjavik", "Iceland", "IS", "Europe", 63.985, -22.6056, "Atlantic/Reykjavik", "ISK", "Icelandic", 1.5, ("Downtown", "Old Harbour", "Laugardalur", "Vesturbaer")),
    City("IST", "Istanbul Airport", "Istanbul", "Turkiye", "TR", "Europe", 41.2753, 28.7519, "Europe/Istanbul", "TRY", "Turkish", 0.7, ("Sultanahmet", "Beyoglu", "Karakoy", "Kadikoy")),
    City("DXB", "Dubai International Airport", "Dubai", "United Arab Emirates", "AE", "Middle East", 25.2532, 55.3657, "Asia/Dubai", "AED", "Arabic, English", 1.25, ("Downtown Dubai", "Dubai Marina", "Deira", "Jumeirah")),
    City("CAI", "Cairo International Airport", "Cairo", "Egypt", "EG", "Africa", 30.1219, 31.4056, "Africa/Cairo", "EGP", "Arabic", 0.5, ("Downtown", "Zamalek", "Giza", "Garden City")),
    City("RAK", "Marrakesh Menara Airport", "Marrakech", "Morocco", "MA", "Africa", 31.6069, -8.0363, "Africa/Casablanca", "MAD", "Arabic, French", 0.6, ("Medina", "Gueliz", "Hivernage", "Kasbah")),
    City("CPT", "Cape Town International Airport", "Cape Town", "South Africa", "ZA", "Africa", -33.9715, 18.6021, "Africa/Johannesburg", "ZAR", "English, Afrikaans", 0.7, ("V&A Waterfront", "City Bowl", "Camps Bay", "Sea Point")),
    City("JFK", "John F. Kennedy International Airport", "New York", "United States", "US", "North America", 40.6413, -73.7781, "America/New_York", "USD", "English", 1.5, ("Midtown", "Lower Manhattan", "Williamsburg", "Upper West Side")),
    City("LAX", "Los Angeles International Airport", "Los Angeles", "United States", "US", "North America", 33.9416, -118.4085, "America/Los_Angeles", "USD", "English", 1.35, ("Santa Monica", "Hollywood", "Downtown LA", "Venice")),
    City("SFO", "San Francisco International Airport", "San Francisco", "United States", "US", "North America", 37.6213, -122.379, "America/Los_Angeles", "USD", "English", 1.45, ("Union Square", "Fisherman's Wharf", "Mission District", "Nob Hill")),
    City("ORD", "O'Hare International Airport", "Chicago", "United States", "US", "North America", 41.9742, -87.9073, "America/Chicago", "USD", "English", 1.2, ("The Loop", "River North", "Lincoln Park", "West Loop")),
    City("MIA", "Miami International Airport", "Miami", "United States", "US", "North America", 25.7959, -80.287, "America/New_York", "USD", "English, Spanish", 1.25, ("South Beach", "Brickell", "Wynwood", "Coconut Grove")),
    City("YYZ", "Toronto Pearson International Airport", "Toronto", "Canada", "CA", "North America", 43.6777, -79.6248, "America/Toronto", "CAD", "English", 1.15, ("Downtown", "Yorkville", "Distillery District", "Queen West")),
    City("MEX", "Mexico City International Airport", "Mexico City", "Mexico", "MX", "Latin America", 19.4361, -99.0719, "America/Mexico_City", "MXN", "Spanish", 0.65, ("Roma Norte", "Condesa", "Centro Historico", "Polanco")),
    City("CUN", "Cancun International Airport", "Cancun", "Mexico", "MX", "Latin America", 21.0365, -86.8771, "America/Cancun", "MXN", "Spanish", 0.85, ("Hotel Zone", "Downtown Cancun", "Puerto Juarez", "Playa Mujeres")),
    City("GIG", "Rio de Janeiro-Galeao International Airport", "Rio de Janeiro", "Brazil", "BR", "Latin America", -22.809, -43.2506, "America/Sao_Paulo", "BRL", "Portuguese", 0.7, ("Copacabana", "Ipanema", "Santa Teresa", "Leblon")),
    City("EZE", "Ministro Pistarini International Airport", "Buenos Aires", "Argentina", "AR", "Latin America", -34.8222, -58.5358, "America/Argentina/Buenos_Aires", "ARS", "Spanish", 0.6, ("Palermo", "Recoleta", "San Telmo", "Puerto Madero")),
    City("HND", "Haneda Airport", "Tokyo", "Japan", "JP", "Asia", 35.5494, 139.7798, "Asia/Tokyo", "JPY", "Japanese", 1.1, ("Shinjuku", "Shibuya", "Asakusa", "Ginza")),
    City("KIX", "Kansai International Airport", "Osaka", "Japan", "JP", "Asia", 34.4347, 135.244, "Asia/Tokyo", "JPY", "Japanese", 0.95, ("Namba", "Umeda", "Shinsekai", "Tennoji")),
    City("ICN", "Incheon International Airport", "Seoul", "South Korea", "KR", "Asia", 37.4602, 126.4407, "Asia/Seoul", "KRW", "Korean", 0.95, ("Myeongdong", "Hongdae", "Gangnam", "Insadong")),
    City("HKG", "Hong Kong International Airport", "Hong Kong", "Hong Kong SAR", "HK", "Asia", 22.308, 113.9185, "Asia/Hong_Kong", "HKD", "Cantonese, English", 1.2, ("Central", "Tsim Sha Tsui", "Causeway Bay", "Sheung Wan")),
    City("SIN", "Singapore Changi Airport", "Singapore", "Singapore", "SG", "Asia", 1.3644, 103.9915, "Asia/Singapore", "SGD", "English, Malay, Mandarin, Tamil", 1.25, ("Marina Bay", "Chinatown", "Orchard", "Kampong Glam")),
    City("BKK", "Suvarnabhumi Airport", "Bangkok", "Thailand", "TH", "Asia", 13.69, 100.7501, "Asia/Bangkok", "THB", "Thai", 0.55, ("Sukhumvit", "Riverside", "Silom", "Old Town")),
    City("DPS", "I Gusti Ngurah Rai International Airport", "Bali", "Indonesia", "ID", "Asia", -8.7482, 115.1675, "Asia/Makassar", "IDR", "Indonesian", 0.55, ("Seminyak", "Ubud", "Canggu", "Uluwatu")),
    City("DEL", "Indira Gandhi International Airport", "Delhi", "India", "IN", "Asia", 28.5562, 77.1, "Asia/Kolkata", "INR", "Hindi, English", 0.45, ("Connaught Place", "Old Delhi", "Hauz Khas", "Aerocity")),
    City("BOM", "Chhatrapati Shivaji Maharaj International Airport", "Mumbai", "India", "IN", "Asia", 19.0896, 72.8656, "Asia/Kolkata", "INR", "Marathi, Hindi, English", 0.5, ("Colaba", "Bandra", "Juhu", "Lower Parel")),
    City("SYD", "Sydney Kingsford Smith Airport", "Sydney", "Australia", "AU", "Oceania", -33.9399, 151.1753, "Australia/Sydney", "AUD", "English", 1.3, ("The Rocks", "Darling Harbour", "Surry Hills", "Bondi")),
]

CITY_BY_IATA: dict[str, City] = {c.iata: c for c in CITIES}


@dataclass(frozen=True)
class Carrier:
    code: str
    name: str
    hub: str
    rating: float
    regions: tuple[str, ...]


# Fictional airlines. Two-letter designators are illustrative only.
CARRIERS: list[Carrier] = [
    Carrier("MR", "Meridian Air", "LHR", 4.3, ("Europe", "North America")),
    Carrier("CB", "Cobalt Airways", "CDG", 4.1, ("Europe", "Africa")),
    Carrier("ZR", "Azura Airlines", "FCO", 3.9, ("Europe",)),
    Carrier("NX", "Nordlys Air", "KEF", 4.0, ("Europe", "North America")),
    Carrier("SJ", "Sirocco Jet", "IST", 4.2, ("Europe", "Middle East", "Africa", "Asia")),
    Carrier("FL", "Falcon Gulf Airways", "DXB", 4.6, ("Middle East", "Europe", "Asia", "Africa", "Oceania", "North America")),
    Carrier("AT", "Atlantica", "JFK", 3.8, ("North America", "Europe", "Latin America")),
    Carrier("PC", "Pacific Crest Airlines", "SFO", 4.0, ("North America", "Asia", "Oceania")),
    Carrier("MA", "Maple Air", "YYZ", 3.9, ("North America", "Europe")),
    Carrier("CN", "Condor Sur", "EZE", 3.7, ("Latin America", "North America")),
    Carrier("SK", "Sakura Skyways", "HND", 4.7, ("Asia", "North America", "Oceania")),
    Carrier("LT", "Lotus Air", "BKK", 4.1, ("Asia", "Oceania")),
    Carrier("MB", "Monsoon Airways", "DEL", 3.8, ("Asia", "Middle East", "Europe")),
    Carrier("SS", "Straits Air", "SIN", 4.8, ("Asia", "Oceania", "Europe")),
    Carrier("SX", "Southern Cross Air", "SYD", 4.2, ("Oceania", "Asia", "North America")),
    Carrier("SV", "Savanna Air", "CPT", 3.8, ("Africa", "Europe", "Middle East")),
]

HUBS_BY_REGION: dict[str, list[str]] = {
    "Europe": ["IST", "LHR", "CDG"],
    "Middle East": ["DXB"],
    "Africa": ["CAI", "DXB"],
    "North America": ["JFK", "ORD", "LAX"],
    "Latin America": ["MEX", "MIA"],
    "Asia": ["SIN", "HKG", "HND"],
    "Oceania": ["SYD", "SIN"],
}

AIRCRAFT_SHORT = ["Airbus A320neo", "Boeing 737 MAX 8", "Airbus A321neo", "Embraer E195-E2"]
AIRCRAFT_MEDIUM = ["Boeing 787-8", "Airbus A330-900", "Airbus A321LR"]
AIRCRAFT_LONG = ["Boeing 787-9", "Airbus A350-900", "Boeing 777-300ER", "Airbus A350-1000"]

CABIN_MULTIPLIER = {"economy": 1.0, "premium_economy": 1.75, "business": 3.6}
CABIN_LABELS = {"economy": "Economy", "premium_economy": "Premium Economy", "business": "Business"}
CHILD_FARE_FACTOR = 0.75

ROOM_TYPES = [
    {"code": "STD", "name": "Standard Room", "multiplier": 1.0, "max_guests": 2, "count": 30, "bed": "1 Queen bed"},
    {"code": "DLX", "name": "Deluxe Room", "multiplier": 1.35, "max_guests": 3, "count": 16, "bed": "1 King bed + sofa bed"},
    {"code": "FAM", "name": "Family Room", "multiplier": 1.6, "max_guests": 4, "count": 8, "bed": "2 Double beds"},
    {"code": "STE", "name": "Suite", "multiplier": 2.4, "max_guests": 3, "count": 4, "bed": "1 King bed, separate lounge"},
]

AMENITIES_BY_STARS = {
    2: ["Free Wi-Fi", "24h front desk", "Luggage storage"],
    3: ["Free Wi-Fi", "24h front desk", "Air conditioning", "Breakfast available", "Luggage storage"],
    4: ["Free Wi-Fi", "Fitness centre", "Restaurant", "Bar", "Air conditioning", "Room service", "Airport shuttle"],
    5: ["Free Wi-Fi", "Spa", "Pool", "Fitness centre", "Fine-dining restaurant", "Concierge", "Room service", "Valet parking"],
}
EXTRA_AMENITIES = ["Rooftop terrace", "Pet friendly", "Wheelchair accessible", "EV charging", "Kids club", "Laundry service", "Business centre", "Garden"]

HOTEL_NAME_PATTERNS = [
    "{hood} Grand Hotel", "The {adj} {noun}", "Hotel {adj} {hood}", "{noun} House {city}",
    "The {hood} Residences", "{adj} Stay {city}", "Casa {noun}", "{city} {noun} Suites",
]
HOTEL_ADJ = ["Amber", "Silver", "Olive", "Harbour", "Juniper", "Cedar", "Linden", "Saffron", "Indigo", "Coral", "Willow", "Ivory"]
HOTEL_NOUN = ["Lantern", "Courtyard", "Terrace", "Atelier", "Gardens", "Loft", "Pavilion", "Quarter", "Harbour", "Mill"]
STREET_NAMES = ["Market Street", "Station Road", "River Walk", "Park Avenue", "Old Town Lane", "Harbour Road", "Garden Street", "King's Way"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def haversine_km(a: City, b: City) -> float:
    r = 6371.0
    p1, p2 = math.radians(a.lat), math.radians(b.lat)
    dp = p2 - p1
    dl = math.radians(b.lon - a.lon)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def stable_unit(*parts: object) -> float:
    """Deterministic pseudo-random number in [0, 1) derived from ``parts``."""
    digest = hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()
    return int(digest[:12], 16) / float(16**12)


def seasonal_factor(d: date) -> float:
    """Peak in Jul/Aug and late December, shoulder in spring/autumn."""
    if d.month in (7, 8) or (d.month == 12 and d.day >= 18):
        return 1.3
    if d.month in (6, 12, 4):
        return 1.12
    if d.month in (1, 2, 11):
        return 0.88
    return 1.0


def weekday_factor(d: date) -> float:
    return {4: 1.1, 5: 1.08, 6: 1.12}.get(d.weekday(), 1.0)  # Fri/Sat/Sun


def advance_purchase_factor(days_ahead: int) -> float:
    if days_ahead < 7:
        return 1.45
    if days_ahead < 21:
        return 1.2
    if days_ahead < 60:
        return 1.0
    return 0.92


def pick_carrier(origin: City, dest: City, salt: int) -> Carrier:
    home = [c for c in CARRIERS if c.hub in (origin.iata, dest.iata)]
    regional = [
        c for c in CARRIERS
        if origin.region in c.regions and dest.region in c.regions
        and CITY_BY_IATA[c.hub].region in (origin.region, dest.region)
    ]
    pool = home + regional or [c for c in CARRIERS if c.code in ("FL", "SJ", "SS")]
    return pool[int(stable_unit(origin.iata, dest.iata, salt) * len(pool))]


# ---------------------------------------------------------------------------
# Generators
# ---------------------------------------------------------------------------
def generate_schedules() -> list[dict]:
    """Every city pair gets 2-4 daily departures; ultra long-haul becomes 1-stop."""
    rows: list[dict] = []
    counters: dict[str, int] = {}
    for origin in CITIES:
        for dest in CITIES:
            if origin.iata == dest.iata:
                continue
            km = haversine_km(origin, dest)
            n_flights = 4 if km < 2500 else 3 if km < 7000 else 2
            for i in range(n_flights):
                carrier = pick_carrier(origin, dest, i)
                stops, via = 0, None
                block = 40 + km / 820 * 60  # taxi + cruise
                if km > 10500 or (km > 7500 and stable_unit(origin.iata, dest.iata, i, "stop") < 0.5):
                    hubs = [h for h in HUBS_BY_REGION[origin.region] + HUBS_BY_REGION[dest.region] if h not in (origin.iata, dest.iata)]
                    via = hubs[int(stable_unit("via", origin.iata, dest.iata, i) * len(hubs))]
                    stops = 1
                    block += 95 + stable_unit("layover", origin.iata, dest.iata, i) * 120
                dep_minutes = int((6 * 60 + (i * 17 * 60 / n_flights) + stable_unit(origin.iata, dest.iata, i, "dep") * 70)) % (24 * 60)
                dep_minutes -= dep_minutes % 5
                base = (55 + km * 0.085) * (0.85 + 0.3 * stable_unit("fare", origin.iata, dest.iata, i))
                if stops:
                    base *= 0.88
                counters[carrier.code] = counters.get(carrier.code, 99) + 1
                if km < 2500:
                    aircraft, seats = AIRCRAFT_SHORT, (150, 0, 12)
                elif km < 7000:
                    aircraft, seats = AIRCRAFT_MEDIUM, (190, 21, 24)
                else:
                    aircraft, seats = AIRCRAFT_LONG, (240, 28, 36)
                days = "1234567" if n_flights > 2 or i == 0 else "12457"
                rows.append(
                    {
                        "flight_number": f"{carrier.code}{counters[carrier.code]}",
                        "airline_code": carrier.code,
                        "origin": origin.iata,
                        "destination": dest.iata,
                        "departure_time": f"{dep_minutes // 60:02d}:{dep_minutes % 60:02d}",
                        "duration_minutes": int(round(block / 5) * 5),
                        "stops": stops,
                        "via": via,
                        "aircraft": aircraft[int(stable_unit("ac", origin.iata, dest.iata, i) * len(aircraft))],
                        "days_of_week": days,
                        "base_fare": round(base, 2),
                        "seats_economy": seats[0],
                        "seats_premium_economy": seats[1],
                        "seats_business": seats[2],
                    }
                )
    return rows


def generate_hotels() -> list[dict]:
    rows: list[dict] = []
    for city in CITIES:
        rng = random.Random(f"hotels-{city.iata}")
        used: set[str] = set()
        star_plan = [2, 3, 3, 3, 4, 4, 4, 5, 5]
        for idx, stars in enumerate(star_plan):
            hood = city.neighborhoods[idx % len(city.neighborhoods)]
            for _ in range(20):
                name = rng.choice(HOTEL_NAME_PATTERNS).format(
                    hood=hood, adj=rng.choice(HOTEL_ADJ), noun=rng.choice(HOTEL_NOUN), city=city.city
                )
                if name not in used:
                    break
            used.add(name)
            amenities = list(AMENITIES_BY_STARS[stars]) + rng.sample(EXTRA_AMENITIES, k=2)
            if stars >= 4 and "Wheelchair accessible" not in amenities:
                amenities.append("Wheelchair accessible")
            base_rate = (28 + stars**2 * 14) * city.cost_index * (0.85 + rng.random() * 0.35)
            rooms = [dict(rt) for rt in ROOM_TYPES if stars >= 4 or rt["code"] != "STE"]
            rating = round(min(9.8, 6.4 + stars * 0.55 + rng.random() * 1.1), 1)
            rows.append(
                {
                    "code": f"{city.iata}{idx + 1:02d}",
                    "name": name,
                    "city_code": city.iata,
                    "neighborhood": hood,
                    "address": f"{rng.randint(2, 240)} {rng.choice(STREET_NAMES)}, {hood}, {city.city}",
                    "stars": stars,
                    "rating": rating,
                    "review_count": rng.randint(180, 5200),
                    "base_rate": round(base_rate, 2),
                    "amenities": amenities,
                    "room_types": rooms,
                    "description": (
                        f"A {stars}-star stay in {hood}, {city.city}. "
                        f"{'Boutique rooms and a relaxed atmosphere' if stars <= 3 else 'Full-service hotel with polished rooms'}"
                        f" within easy reach of the city's main sights."
                    ),
                    "free_cancellation": stars >= 3 or rng.random() < 0.5,
                    "breakfast_included": rng.random() < (0.3 + stars * 0.1),
                }
            )
    return rows


# Typical per-person daily spend (USD) at cost_index 1.0, by travel style.
DAILY_COSTS = {
    "budget": {"food": 35.0, "local_transport": 8.0, "activities": 20.0},
    "comfort": {"food": 65.0, "local_transport": 15.0, "activities": 45.0},
    "luxury": {"food": 140.0, "local_transport": 45.0, "activities": 110.0},
}


def rooms_needed(guests: int) -> int:
    """Rooms to request for a party (family rooms sleep up to four)."""
    return max(1, -(-guests // 4))
