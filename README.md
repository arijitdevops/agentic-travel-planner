# Agentic Travel Planner

A multi-agent travel planning app. You describe the trip you want: where from, where to, dates, travelers, budget, interests, pace, and any dietary or accessibility needs. A crew of six AI agents built on **CrewAI** and **Google Gemini** turns that into a complete plan: a traveler profile, destination research, the best flight for every leg, the best hotel for every stay, a day-by-day itinerary and a budget check. You can refine the plan by chatting with a concierge agent, then book the flights and hotels in the app.

[![Python 3.10-3.13](https://img.shields.io/badge/python-3.10--3.13-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.141-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![CrewAI](https://img.shields.io/badge/CrewAI-1.15-FF5A50)](https://www.crewai.com/)
[![Gemini](https://img.shields.io/badge/Google-Gemini%202.5%20Flash-4285F4?logo=googlegemini&logoColor=white)](https://ai.google.dev/)
[![React 19](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)](https://react.dev/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.9-3178C6?logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![MySQL 8](https://img.shields.io/badge/MySQL-8-4479A1?logo=mysql&logoColor=white)](https://www.mysql.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> **Bookings are simulated.** Bookings are real database records. They get PNR-style references and ticket numbers, and they use up seats and rooms in the inventory. However, **no payment is taken and nothing is booked with a real airline or hotel.** The default flight and hotel inventory is generated mock data: the airports and neighbourhoods are real, but the carriers, hotels, schedules and prices are fictional.

---

## Contents

- [Features](#features)
- [How it works](#how-it-works)
- [The agents](#the-agents)
- [Tech stack](#tech-stack)
- [Project structure](#project-structure)
- [Getting started](#getting-started)
- [Configuration](#configuration)
- [Usage](#usage)
- [API reference](#api-reference)
- [Travel data providers](#travel-data-providers)
- [Testing](#testing)
- [Limitations](#limitations)
- [License](#license)

## Features

- **Plan-a-trip form** covering origin, 1-4 destinations in order, dates, adults and children, total budget, cabin class, minimum hotel stars, travel style (budget, comfort or luxury), pace (relaxed, balanced or packed), interests, dietary needs, accessibility needs and free-text notes.
- **Six-agent CrewAI crew** running in a sequential process with typed (Pydantic) outputs at every step.
- **Live progress.** The planning job runs in the background, and every agent start or finish and every tool call is stored as an event. The UI follows the job over **Server-Sent Events**, and switches to polling if the stream is unavailable.
- **Plans use real, bookable offers.** Before the agents run, the backend fetches current flight and hotel offers from the provider. The agents choose from these offers, or search for more with their tools. Every offer id they return is checked. If an agent makes up an id, the backend falls back to the top-ranked real option.
- **Budget reconciliation.** The flight and hotel lines in the budget always use the quoted prices of the selected offers, not the LLM's own arithmetic.
- **Chat refinement.** A concierge agent answers questions and can edit the itinerary or swap flights and hotels. Each accepted change increases the plan version and recalculates the budget.
- **Booking flow.** Before you confirm, the offer is re-priced and its availability is checked. The app then collects passenger or guest details, confirms with a reference, and lists the booking under *My bookings*. Cancellation follows a documented refund policy.
- **Direct search.** You can search and book flights and hotels without the AI. Search and booking work even when no Gemini key is configured.
- **Graceful degradation.** Without `GEMINI_API_KEY` the app still starts. A planning request collects flight and hotel options you can book, then stops with a clear message.
- **Lightweight identity.** Each browser identifies itself with an email address sent in the `X-User-Email` header, so trips and bookings are separated per user. There are no passwords, which is fine for a demo.

## How it works

```mermaid
flowchart LR
    subgraph Browser["React + TypeScript (Vite)"]
        UI[Plan form / Trip view / Chat / Bookings]
    end

    subgraph API["FastAPI backend"]
        R[REST routes]
        SSE[SSE progress stream]
        BG[Background planning job]
        BK[Booking engine]
        subgraph Crew["CrewAI crew (sequential)"]
            A1[Traveler Profile Analyst] --> A2[Destination Research Specialist]
            A2 --> A3[Flight Booking Specialist]
            A3 --> A4[Accommodation Specialist]
            A4 --> A5[Itinerary Architect]
            A5 --> A6[Travel Budget Analyst]
        end
        C[Trip Concierge - chat refinement]
    end

    subgraph Providers["Travel providers"]
        L[(Local mock inventory)]
        D[Duffel API - optional]
    end

    LLM[[Google Gemini 2.5 Flash]]
    WEB[[DuckDuckGo / Tavily]]
    DB[(MySQL 8)]

    UI -- JSON --> R
    UI -- EventSource --> SSE
    R --> BG --> Crew
    R --> C
    R --> BK
    Crew -- LLM calls --> LLM
    C -- LLM calls --> LLM
    A2 -- web_search --> WEB
    A3 & A4 & C -- search tools --> Providers
    BG -- prefetch offers --> Providers
    BK --> Providers
    L --- DB
    BG & SSE & BK --> DB
```

What happens for one planning request:

```mermaid
sequenceDiagram
    participant U as Browser
    participant API as FastAPI
    participant J as Planning job
    participant P as Providers
    participant C as CrewAI crew
    participant DB as MySQL

    U->>API: POST /api/trips
    API->>DB: insert trip (queued)
    API-->>U: 202 Accepted {id}
    API->>J: background task
    U->>API: GET /api/trips/{id}/stream (SSE)
    J->>P: search flights per leg, hotels per stay
    J->>DB: store options + events
    J->>C: kickoff(inputs)
    loop each agent
        C->>DB: agent_started / tool / agent_completed events
        API-->>U: event: progress
    end
    J->>J: validate offer ids, reconcile budget
    J->>DB: store plan (completed)
    API-->>U: event: status {completed}
    U->>API: GET /api/trips/{id}
```

## The agents

Agent roles, goals and backstories are defined in [`backend/app/agents/config/agents.yaml`](backend/app/agents/config/agents.yaml). Task prompts are in [`tasks.yaml`](backend/app/agents/config/tasks.yaml). Structured outputs are defined in [`schemas.py`](backend/app/agents/schemas.py).

| # | Agent | Responsibility | Tools | Output model |
|---|-------|----------------|-------|--------------|
| 1 | **Traveler Profile Analyst** | Turns the form and notes into priorities, must-haves, things to avoid and a daily rhythm | none | `TravelerProfile` |
| 2 | **Destination Research Specialist** | Areas to stay, experiences matched to interests, food, local tips, weather, entry notes, with sources | `city_guide`, `web_search` | `DestinationResearch` |
| 3 | **Flight Booking Specialist** | Chooses one flight per leg (price vs. duration, stops, departure time) plus alternatives | `search_flights` | `FlightSelection` |
| 4 | **Accommodation Specialist** | Chooses one hotel per stay (location, rating, star floor, accessibility, price) | `search_hotels` | `HotelSelection` |
| 5 | **Itinerary Architect** | Day-by-day plan that follows a fixed day skeleton, works around flight times and respects pace and dietary needs | `city_guide` | `Itinerary` |
| 6 | **Travel Budget Analyst** | Cost breakdown by category, compared with the budget, plus savings tips | `estimate_daily_costs` | `BudgetBreakdown` |
| - | **Trip Concierge** (chat) | Answers follow-up questions, edits the itinerary, swaps flights or hotels | `search_flights`, `search_hotels`, `web_search`, `estimate_daily_costs` | `RefinementResult` |

Each task receives the earlier outputs it needs as CrewAI `context`. For example, the itinerary task sees the profile, the research and the flight and hotel choices. Delegation is disabled so each agent stays within its own job.

## Tech stack

| Layer | Choice |
|-------|--------|
| Agents | CrewAI 1.15 (`Agent`, `Task`, `Crew`, `Process.sequential`, `BaseTool`, `output_pydantic`) |
| LLM | Google Gemini `gemini-2.5-flash` through CrewAI's native Gemini provider (`crewai[google-genai]`) |
| Web search | `ddgs` (DuckDuckGo, no key) or Tavily if `TAVILY_API_KEY` is set |
| API | FastAPI, Uvicorn, Pydantic v2, pydantic-settings |
| Database | MySQL 8 using SQLAlchemy 2.0 and PyMySQL. SQLite is supported for local runs and tests |
| Frontend | React 19, TypeScript 5.9, Vite 8, React Router 7, react-markdown |
| Tests | pytest (backend, 63 tests), Vitest (frontend helpers) |
| Deployment | Docker Compose: MySQL, API, and nginx serving the SPA and proxying `/api` |

## Project structure

```
agentic-travel-planner/
├── backend/
│   ├── app/
│   │   ├── main.py               # FastAPI app factory, startup (create tables, seed, recover jobs)
│   │   ├── config.py             # Settings (env / .env)
│   │   ├── db.py                 # SQLAlchemy engine and sessions
│   │   ├── models.py             # ORM: inventory + users, trips, events, messages, bookings
│   │   ├── schemas.py            # API request/response models
│   │   ├── deps.py               # current user (X-User-Email / demo user)
│   │   ├── seed.py               # python -m app.seed  -> load mock inventory
│   │   ├── api/                  # routes: health, users, inventory, trips, bookings
│   │   ├── agents/
│   │   │   ├── config/agents.yaml
│   │   │   ├── config/tasks.yaml
│   │   │   ├── crew.py           # TravelPlanningCrew, RefinementCrew
│   │   │   ├── tools.py          # search_flights, search_hotels, web_search, city_guide, estimate_daily_costs
│   │   │   ├── schemas.py        # agent output models
│   │   │   └── llm.py            # Gemini LLM factory
│   │   ├── providers/
│   │   │   ├── base.py           # FlightProvider / HotelProvider interfaces, offer models
│   │   │   ├── local.py          # mock inventory provider (default)
│   │   │   ├── duffel.py         # optional Duffel flight search
│   │   │   └── mock_data.py      # deterministic cities, carriers, schedules, hotels, pricing
│   │   └── services/
│   │       ├── planner.py        # planning job + chat refinement orchestration
│   │       ├── booking.py        # simulated booking, cancellation, refunds
│   │       └── events.py         # progress events
│   ├── scripts/export_schema.py  # regenerate schema.sql from the models
│   ├── tests/                    # pytest suite (fake LLM, SQLite)
│   ├── schema.sql                # MySQL 8 DDL
│   ├── requirements.txt / requirements-dev.txt
│   ├── pyproject.toml            # pytest config
│   ├── Dockerfile
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── pages/                # PlanTrip, Trip, Trips, Explore, Bookings
│   │   ├── components/           # AgentProgress, ItineraryView, FlightCard, HotelCard,
│   │   │                         # BookingDialog, ChatPanel, BudgetView, InsightsView, ...
│   │   ├── api/client.ts         # typed API client
│   │   ├── lib/                  # formatting helpers (+ tests)
│   │   └── types.ts
│   ├── nginx.conf / Dockerfile
│   ├── package.json / package-lock.json
│   └── .env.example
├── docker-compose.yml
├── LICENSE
└── README.md
```

## Getting started

### Prerequisites

- **Python 3.10-3.13.** CrewAI does not support 3.14 yet.
- **Node.js 20.19+ or 22.12+** with npm. Vite 8 requires one of these versions.
- **MySQL 8** installed locally or through Docker. For a quick try you can use SQLite instead.
- A **Gemini API key** from [Google AI Studio](https://aistudio.google.com/app/apikey). You only need it for the AI features.

### Option A: Docker Compose (everything)

```bash
cp backend/.env.example backend/.env      # Windows: copy backend\.env.example backend\.env
# edit backend/.env and set GEMINI_API_KEY
docker compose up --build
```

- App: <http://localhost:8080>
- API docs (Swagger): <http://localhost:8000/docs>

The backend creates the tables and loads the mock inventory the first time it starts. Compose sets `DATABASE_URL` to point at the `mysql` service, overriding the value in `.env`. Loading an optional env file this way (`required: false`) needs Docker Compose v2.24 or newer.

### Option B: Run locally

#### 1. Database

If you have MySQL, create the database and user:

```sql
CREATE DATABASE travel_planner CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'travel'@'localhost' IDENTIFIED BY 'travel';
GRANT ALL PRIVILEGES ON travel_planner.* TO 'travel'@'localhost';
```

To run only MySQL in Docker, use `docker compose up -d mysql`.

The tables are created automatically when the app starts. [`backend/schema.sql`](backend/schema.sql) is also provided if you prefer to create them yourself on an empty database.

To skip MySQL entirely, set `DATABASE_URL=sqlite:///./travel_planner.db` in `backend/.env`.

#### 2. Backend

**macOS / Linux**

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # then set GEMINI_API_KEY (and DATABASE_URL if needed)
python -m app.seed            # optional: startup seeds automatically
uvicorn app.main:app --reload --port 8000
```

**Windows (PowerShell)**

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env        # then set GEMINI_API_KEY (and DATABASE_URL if needed)
python -m app.seed            # optional: startup seeds automatically
uvicorn app.main:app --reload --port 8000
```

When the server is running, <http://localhost:8000/api/health> reports the database status, whether the LLM is configured, and which providers are active.

#### 3. Frontend

Open a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open <http://localhost:5173>. The Vite dev server proxies `/api` to `http://localhost:8000`. To change that, set `VITE_PROXY_TARGET` in `frontend/.env`.

## Configuration

Backend settings are read from environment variables or `backend/.env`. See [`backend/.env.example`](backend/.env.example).

| Variable | Default | Description |
|----------|---------|-------------|
| `GEMINI_API_KEY` | *(empty)* | Google AI Studio key. Without it the AI agents are disabled, but search and booking still work |
| `GEMINI_MODEL` | `gemini/gemini-2.5-flash` | CrewAI model string. A bare name such as `gemini-2.5-pro` gets the `gemini/` prefix added |
| `LLM_TEMPERATURE` | `0.4` | Sampling temperature |
| `AGENT_MAX_ITER` | `8` | Maximum reasoning/tool iterations per agent |
| `CREW_VERBOSE` | `false` | Print CrewAI's step-by-step log to the console |
| `DATABASE_URL` | `mysql+pymysql://travel:travel@localhost:3306/travel_planner?charset=utf8mb4` | Any SQLAlchemy URL. `sqlite:///./travel_planner.db` also works |
| `SEED_ON_STARTUP` | `true` | Load the mock inventory if the tables are empty |
| `TAVILY_API_KEY` | *(empty)* | Use Tavily for web search. If empty, DuckDuckGo is used (no key needed) |
| `WEB_SEARCH_ENABLED` | `true` | Turn web search off entirely |
| `WEB_SEARCH_MAX_RESULTS` | `5` | Results returned per search |
| `FLIGHT_PROVIDER` | `local` | `local` (mock inventory) or `duffel` |
| `DUFFEL_ACCESS_TOKEN` | *(empty)* | Required when `FLIGHT_PROVIDER=duffel`. Use a `duffel_test_...` token |
| `OFFER_TTL_MINUTES` | `30` | How long a Duffel offer can be booked after searching |
| `CORS_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | Comma-separated list of allowed origins |
| `DEMO_USER_EMAIL` / `DEMO_USER_NAME` | `demo@travelplanner.local` / `Demo Traveler` | User assumed when no `X-User-Email` header is sent |

Frontend settings (`frontend/.env`): `VITE_API_BASE_URL` (leave empty to use the proxy) and `VITE_PROXY_TARGET`.

## Usage

1. **Plan a trip.** Fill in the form. For example: London to Paris then Rome, 6 nights, 2 adults, $5,000, food and history, vegetarian. Then click **Plan my trip**.
2. **Watch the agents.** The progress card shows each agent working, and the activity log lists tool calls such as flight searches and web searches. A run usually takes one to three minutes with Gemini 2.5 Flash. You can leave the page and come back.
3. **Review the plan** in these tabs:
   - **Itinerary**: day by day, with times, locations and estimated costs.
   - **Flights**: every leg, with the agent's pick highlighted and its reasoning.
   - **Hotels**: every stay, with the agent's pick highlighted.
   - **Budget**: the category breakdown compared with your budget.
   - **Insights**: your traveler profile and the destination research, with sources.
4. **Refine it by chat.** Try "Make day 2 more relaxed", "Find a cheaper hotel in Rome" or "Swap the museum on day 3 for a food tour". Changes are applied to the plan and listed under the reply.
5. **Book.** Click **Book** on any flight or hotel card. The dialog re-checks the price and availability, asks for traveler names and a contact email, and confirms with a reference such as `K7M2QX` for a flight or `HP4ZT8A` for a hotel.
6. **Manage bookings** under *My bookings*, where you can cancel and see the refund amount.
7. **Search directly** under *Flights & hotels* to find and book without running the AI.

To work as a different user, click the user chip in the header and enter an email address. Trips and bookings are kept separate per email.

## API reference

Interactive documentation is available at `/docs` (Swagger UI) and `/redoc`. All routes are prefixed with `/api`. Send `X-User-Email: you@example.com` to act as a user. Without it, requests use the demo user.

### Health and user

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Database, LLM, provider and web-search status |
| GET | `/api/me` | Current user (created on first use) |
| PUT | `/api/me` | Rename the current user `{ "name": "..." }` |

### Inventory (no AI)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/locations?q=` | Supported cities and airports (IATA codes) |
| GET | `/api/flights/search` | `origin`, `destination`, `departure_date`, `adults`, `children`, `cabin_class`, `max_results` |
| GET | `/api/flights/offers/{offer_id}` | Re-price and re-check one flight offer |
| GET | `/api/hotels/search` | `city`, `check_in`, `check_out`, `guests`, `rooms`, `min_stars`, `max_nightly_rate`, `max_results` |
| GET | `/api/hotels/offers/{offer_id}` | Re-price and re-check one hotel offer |

### Trips (multi-agent planning)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/trips` | Create a trip and start the planning job. Returns **202** with the trip (`status: queued`) |
| GET | `/api/trips` | Your trips, newest first |
| GET | `/api/trips/{id}` | Trip with `status`, `current_step`, `error` and the full `plan` |
| DELETE | `/api/trips/{id}` | Delete a finished trip. Its bookings are kept and unlinked |
| POST | `/api/trips/{id}/replan` | Run the crew again |
| GET | `/api/trips/{id}/events?after=N` | Progress events after sequence number N (for polling) |
| GET | `/api/trips/{id}/stream?after=N&user=email` | **SSE**: `progress` events, then one `status` event. Supports `Last-Event-ID` |
| GET | `/api/trips/{id}/messages` | Chat history |
| POST | `/api/trips/{id}/messages` | `{ "message": "..." }`. The concierge replies and may update the plan. Returns `503` if no Gemini key is set |

Example request:

```bash
curl -X POST http://localhost:8000/api/trips \
  -H "Content-Type: application/json" -H "X-User-Email: ada@example.com" \
  -d '{"origin":"LHR","destinations":["CDG","FCO"],"start_date":"2026-11-02","end_date":"2026-11-08",
       "adults":2,"budget":5000,"interests":["food","history"],"pace":"balanced",
       "travel_style":"comfort","dietary_needs":"vegetarian"}'
```

The request is validated as follows:

- 1 to 30 nights, with at least one night per destination.
- Destinations must be unique, and the origin cannot also be a destination.
- All codes must be supported cities.

The `plan` object contains `legs`, `stays`, `day_skeleton`, `flight_options`, `hotel_options`, `profile`, `research`, `flights`, `hotels`, `itinerary`, `budget`, `generated_at` and `model`.

### Bookings (simulated)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/bookings` | `{ offer_id, trip_id?, contact_email, contact_phone?, travelers: [{first_name, last_name, traveler_type, date_of_birth?}] }` |
| GET | `/api/bookings?status=&trip_id=` | Your bookings |
| GET | `/api/bookings/{reference}` | One booking |
| POST | `/api/bookings/{reference}/cancel` | Cancel and calculate the refund |

The booking rules are:

- The traveler mix must match the offer: adults and children for flights, the guest count for hotels.
- A sold-out offer returns `409`.
- Concurrent bookings on the same flight or hotel are serialized with a row lock (`SELECT ... FOR UPDATE` on MySQL).

**Refund policy (simulated):**

- **Flights**: full refund within 24 hours of booking. After that, business class is refunded 100%, premium economy 50% and economy 0%.
- **Hotels**: full refund if the rate has free cancellation and check-in is more than 48 hours away. Otherwise the first night is charged.

## Travel data providers

Flights and hotels come through two small interfaces, `FlightProvider` and `HotelProvider`, defined in [`providers/base.py`](backend/app/providers/base.py).

### Local mock inventory (default)

[`mock_data.py`](backend/app/providers/mock_data.py) generates the same data on every install:

- **36 cities** across Europe, the Americas, the Middle East, Africa, Asia and Oceania, with real airports, time zones, currencies and neighbourhoods.
- **16 fictional carriers** flying **3,172 schedules**. Every city pair is served, and ultra-long-haul routes have one stop via a regional hub.
- **324 fictional hotels** rated 2 to 5 stars, with room types, amenities, ratings, free-cancellation and breakfast flags.

Prices are calculated rather than random. They depend on:

- distance and cabin class
- season and weekend travel
- how far ahead you book
- a stable per-flight or per-hotel variation
- load factor: prices rise as seats or rooms are booked

Availability is real: confirmed bookings reduce the remaining seats and rooms. Offer ids (for example `LF.MR101.20261023.economy.2.0`) contain everything needed to re-price the offer, so they never expire.

### Duffel (optional, flights)

Set `FLIGHT_PROVIDER=duffel` and `DUFFEL_ACCESS_TOKEN` to search flights through the [Duffel API](https://duffel.com/docs). With a test-mode token you get sandbox results. Search results are saved in `offer_snapshots` so they can be booked by id until `OFFER_TTL_MINUTES` passes. Booking stays **simulated**: the app never calls Duffel's order endpoint. This provider is covered by unit tests using mocked responses modelled on the documented API, but it has not been exercised against the live Duffel service. Hotels always come from the local inventory.

> Amadeus Self-Service was the usual free option for this kind of project. It was decommissioned on 17 July 2026, which is why Duffel is the optional live provider here.

## Testing

### Backend

```bash
cd backend
pip install -r requirements-dev.txt
pytest
```

The suite runs against a temporary SQLite database and **never calls Gemini or the web**. [`tests/fakes.py`](backend/tests/fakes.py) provides `FakeLLM`, a subclass of CrewAI's `BaseLLM`. It answers each agent by reading the prompt it receives, for example copying offer ids from the flight options. This means the real CrewAI `Crew`, `Agent`, `Task` and structured-output machinery runs end to end. The tests cover:

- **Mock provider**: deterministic generation, pricing rules, availability, offer-id round-trips and validation.
- **Booking engine**: seat and room consumption, traveler-mix checks, sold-out handling, cancellation and refund policies.
- **API**: inventory, bookings, trips, per-user isolation, request validation, the SSE stream and chat refinement (question-only, hotel swap plus itinerary edit).
- **Crew wiring**: agent order, tools per agent, task context, that every YAML placeholder is filled, fallback when the LLM invents offer ids, budget reconciliation, running without an LLM, and LLM failures.
- **Tools and the Duffel adapter**, using a mocked HTTP transport.

Current result: **63 passed**.

### Frontend

```bash
cd frontend
npm test          # Vitest unit tests for formatting helpers and API error parsing
npm run build     # type-check (tsc -b) and production build
```

## Limitations

- **No real payments or ticketing.** Bookings are simulated by design.
- **The mock inventory is fictional.** Its schedules and prices look realistic but do not represent any real airline or hotel.
- **Planning jobs run inside the API process** using FastAPI background tasks. A restart marks any running job as failed, and you can use *Re-plan* to try again. For heavier use, move the job runner to a queue such as Celery or RQ.
- **Identity is a header, not authentication.** Put real authentication in front of the app before exposing it publicly.
- **LLM output varies.** Offer ids, day counts and budget totals are checked by code, but descriptive content such as activities, tips and entry requirements comes from the model and web search. Verify visa and entry rules with official sources.
- **Prices are in USD**, and the Duffel provider passes through whatever currency Duffel returns.

## License

[MIT](LICENSE) © 2026 Common Labs
