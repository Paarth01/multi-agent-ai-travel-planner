# TripSync AI — Multi-Agent Travel Planner

Given a budget, destination, dates, and interests, TripSync builds a complete
itinerary through specialized sub-agents (flights, hotels, activities,
pricing) coordinated by a LangGraph orchestrator — with real cross-agent
budget negotiation when the initial plan doesn't fit.

## Project structure

```
multi-agent-ai-travel-planner/
├── schemas/          Pydantic models shared across agents and the API
│   └── messages.py
├── graph/             LangGraph orchestration
│   ├── state.py           shared state definition + initial state builder
│   ├── flight_agent.py    flight search (mocked data)
│   ├── hotel_agent.py     hotel search (mocked data)
│   ├── activity_agent.py  activity suggestions (mocked data)
│   ├── pricing_agent.py   budget evaluation + reallocation + routing logic
│   ├── synthesis.py       assembles the final Itinerary
│   └── build.py           wires all nodes into the compiled StateGraph
├── api/
│   └── main.py         FastAPI app, POST /plan-trip streams progress via SSE
├── clients/            Real API clients (own service, Amadeus, Google Places)
│   ├── own_flight_data_client.py  Client for our self-hosted flight data service
│   ├── own_hotel_data_client.py   Client for our self-hosted hotel data service
│   ├── amadeus_client.py       OAuth2 token caching, IATA resolution, flight/hotel search
│   └── google_places_client.py Text search for activities
├── cache/              Caching layer for all live API responses
│   ├── factory.py               Picks Redis or in-memory, falls back gracefully
│   ├── redis_cache.py / memory_cache.py
│   └── keys.py                  Deterministic cache key builder
├── data_service/       Self-hosted flight + hotel + activity data microservice
│   ├── app.py                  FastAPI service sampling from real fare/pricing statistics
│   └── seed_data/               Aggregated real flight fares, hotel bookings, activity fees
├── scripts/
│   ├── build_flight_seed.py    Regenerates flight seed data from the raw Kaggle CSV
│   └── build_hotel_seed.py     Regenerates hotel seed data from the raw AtliQ CSVs
├── config.py           Settings (API credentials, all optional — mock fallback if unset)
├── tests/              115 tests across schemas, cache, clients, data service, agents, graph, and API
├── frontend/            React + TypeScript + Tailwind UI (design via Stitch)
├── requirements.txt
└── README.md            (you are here)
```

## How it works

1. `POST /plan-trip` kicks off a LangGraph run: `flight_agent`, `hotel_agent`,
   and `activity_agent` execute in parallel.
2. `pricing_agent` evaluates the combined cost. If over budget, it flags the
   single category with the largest budget variance for reallocation.
3. `reallocate` shrinks that category's ceiling and re-invokes only that one
   agent — not a full re-run — then loops back to `pricing_agent`.
4. This repeats up to `max_negotiation_rounds` (default 3), then `synthesize`
   assembles the final itinerary, marking it `best_effort` if still over
   budget.
5. Progress streams to the frontend as Server-Sent Events the whole way, so
   the UI can show each agent moving through
   `waiting → searching → found / reallocating` live.

## Running the backend

```bash
pip install -r requirements.txt --break-system-packages
uvicorn api.main:app --reload
```

Runs on `http://localhost:8000`. Health check: `GET /health`.

### Using real flight/hotel/activity data (optional)

By default, every agent runs entirely on mock data — no setup needed,
works out of the box. There are three tiers of real data, from easiest
to hardest to set up:

**1. Own data service — recommended, no signup needed.** Real 2022
Indian domestic flight fares (Kaggle dataset), real AtliQ Grands hotel
booking prices/names/ratings, and real hand-curated ASI/museum entry
fees for major monuments — all self-hosted, no rate limits. See
`data_service/README.md`.

```bash
uvicorn data_service.app:app --port 8100 --reload   # separate terminal
```

Then in `.env`:
```
OWN_FLIGHT_SERVICE_URL=http://localhost:8100
OWN_HOTEL_SERVICE_URL=http://localhost:8100
OWN_ACTIVITY_SERVICE_URL=http://localhost:8100
```

Flights cover 6 metro cities, hotels cover 4, activities cover 4 cities
but only `history`/`nature` categories (no fee-gated beaches/nightlife/
food data exists) — falls through to Amadeus/Google Places or mock
automatically for anything outside that coverage.

**2. Amadeus / Google Places — broader coverage, needs free signup.**

```bash
cp .env.example .env
```

Then fill in:
- `AMADEUS_CLIENT_ID` / `AMADEUS_CLIENT_SECRET` — free test credentials
  at https://developers.amadeus.com/self-service. Powers flight and
  hotel search (`clients/amadeus_client.py`).
- `GOOGLE_PLACES_API_KEY` — from Google Cloud Console with the Places
  API enabled. Powers activity suggestions (`clients/google_places_client.py`).

Each agent tries live sources in priority order (own service → Amadeus/
Google Places → mock) and falls back automatically on any failure
(missing credentials, city not found, zero results, no route/city/
category coverage, network error, rate limit). Check the `data_source`
field in each agent's `AgentMessage.payload` (`"own_service"` /
`"amadeus"` / `"google_places"` / `"mock"`) to see which path was
actually used for a given run.

**Known limitations of the live mapping** (see `data_service/README.md`
for full detail):
- The own data service samples from real *statistics* for flights/
  hotels (not live prices), and real *fixed fees* for activities (hand-
  curated, not bulk-sourced — see the source note in
  `activity_fees.json`). Coverage: flights 6 metros, hotels 4, activities
  4 cities but only `history`/`nature` categories.
- Amadeus's hotel-offers endpoint doesn't return neighborhood/rating
  data on the same call — would need a second call to the Hotel
  Content API for full parity with the mock data's `area`/`rating` fields.
- Google Places has no price or visit-duration field, so activity
  costs are estimated from `price_level` (0–4) via a rough heuristic,
  and duration defaults to 2 hours. Fine for a demo; not real pricing.

### Caching

All live API responses (own service, Amadeus, Google Places) are
cached — see `cache/`. No setup needed: defaults to an in-memory cache.
Set `REDIS_URL` in `.env` to use Redis instead (falls back to
in-memory automatically if Redis is configured but unreachable, rather
than failing trip planning over a cache outage).

Two TTLs, both overridable in `.env`:
- `PRICE_CACHE_TTL_SECONDS` (default 900 / 15 min) — flight/hotel
  prices, activity search results
- `REFERENCE_CACHE_TTL_SECONDS` (default 86400 / 24h) — Amadeus
  city-code lookups, which don't change day to day

Cache keys are built from the search parameters (route/city/dates),
not the budget ceiling — so a reallocation round re-querying the same
route/city during the negotiation loop hits the cache instead of
re-fetching from a rate-limited provider, while each agent still
re-filters the (possibly cached) results against its current ceiling
fresh every time.

## Running the tests

```bash
pytest tests/ -v
```

36 tests: Pydantic schemas, pricing/reallocation logic (including the
ceiling-drift edge case), all three domain agents, full graph integration
(parallel fan-out/fan-in via LangGraph's `operator.add` reducer), and the
FastAPI SSE endpoint.

## Running the frontend

```bash
cd frontend
npm install
cp .env.example .env   # point VITE_API_BASE_URL at the backend above
npm run dev
```

See `frontend/README.md` for architecture notes on how the SSE stream maps
to the live agent-progress UI.

## Known gaps / next steps

- No auth, no persistence — itineraries aren't saved anywhere yet.
- Dark mode design exists in the Stitch export but isn't wired into the
  frontend's Tailwind config yet.
- CORS is wide open (`*`) for local dev — tighten before deploying.
- In-memory cache (the default) isn't shared across worker processes —
  fine for a single `uvicorn` process, but a multi-worker deployment
  would need `REDIS_URL` set for the cache to actually help.
- Activity fee data is hand-curated and narrow (4 cities, 2 categories)
  — no clean bulk dataset exists for this the way it does for flights/
  hotels. See `data_service/README.md` for why, and for how to extend
  it if you find/verify more real fee data.
