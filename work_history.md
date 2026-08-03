# TripSync AI — Project Work History

### Add .gitignore
**Date:** August 03, 2026
**Author:** Paarth Agl
**Commit:** ce213f0


---

### Scaffold project: Pydantic schemas for trip requests, agent messages, and domain models
**Date:** August 03, 2026
**Author:** Paarth Agl
**Commit:** 380954c


---

### Add LangGraph shared state and pricing/reallocation agent
**Date:** August 03, 2026
**Author:** Paarth Agl
**Commit:** 25b1b21

- TravelPlannerState with operator.add reducer for parallel agent writes
- Pricing agent evaluates budget, flags worst-variance category for reallocation
- One-at-a-time reallocation strategy with capped negotiation rounds
- 13 unit tests including a ceiling-drift edge case

---

### Add flight, hotel, and activity domain agents
**Date:** August 03, 2026
**Author:** Paarth Agl
**Commit:** ee0c2dd

- Each agent searches within its budget ceiling, falls back to cheapest
  option when nothing fits so the pricing agent can flag it
- Realistic price floors so tiny budgets are genuinely unaffordable
  rather than scaling proportionally down to nothing

---

### Wire the full LangGraph StateGraph: fan-out, negotiation loop, synthesis
**Date:** August 03, 2026
**Author:** Paarth Agl
**Commit:** a196f33

- Parallel fan-out from START to flight/hotel/activity agents, fan-in to pricing
- Conditional routing: reallocate -> flagged single agent -> pricing (loop)
  or synthesize -> END
- Integration tests confirming parallel writes merge correctly and the
  loop terminates within max_negotiation_rounds

---

### Add FastAPI backend with SSE streaming for live agent progress
**Date:** August 03, 2026
**Author:** Paarth Agl
**Commit:** d7c130a

POST /plan-trip streams node_complete events per agent, then
itinerary_ready with the final plan -- lets the frontend show each
agent moving through waiting -> searching -> found/reallocating live

---

### Add React/TypeScript frontend consuming the SSE stream
**Date:** August 03, 2026
**Author:** Paarth Agl
**Commit:** 6227a33

- Design ported from Stitch export: Tailwind tokens, dark/teal aesthetic
- useTripPlannerSSE hook hand-parses the event stream (EventSource is
  GET-only, backend needs POST)
- Screens: trip request form, live agent progress, itinerary with
  Chart.js budget breakdown, loading skeleton, error state

---

### Integrate Amadeus and Google Places as live data sources
**Date:** August 03, 2026
**Author:** Paarth Agl
**Commit:** 5276f0a

- OAuth2 token caching + IATA city-code resolution for Amadeus
- Each agent tries live data when configured, falls back to mock on
  any failure (missing creds, zero results, network error)
- Fixed a real bug caught by tests: data_source was marked 'live'
  before confirming the live call actually returned results

---

### Build self-hosted flight data service on real Kaggle dataset
**Date:** August 03, 2026
**Author:** Paarth Agl
**Commit:** c5c888c

- Aggregated ~300K rows of real 2022 Indian domestic fares (Kaggle
  'Flight Price Prediction') into compact per-route statistics (24MB -> 57KB)
- Service samples fresh prices from real per-route distributions rather
  than replaying fixed rows
- Flight agent now tries: own service -> Amadeus -> mock, in that order
- Note: data_service/app.py already includes hotel/activity endpoints
  added in the next two commits -- same file, built up incrementally

---

### Extend own data service with real hotel pricing (AtliQ Grands dataset)
**Date:** August 03, 2026
**Author:** Paarth Agl
**Commit:** 3f8c7eb

- ~134K real hotel bookings aggregated into per-city/room-class stats
- Real hotel names and real customer ratings, not synthetic ones
- Hotel agent now tries: own service -> Amadeus -> mock

---

### Extend own data service with hand-curated real activity fees
**Date:** August 03, 2026
**Author:** Paarth Agl
**Commit:** 82a1215

- No bulk activity-pricing dataset exists publicly, unlike flights/hotels
- Hand-compiled real ASI (Archaeological Survey of India) and museum
  entry fees for 8 landmarks across 4 cities, cross-referenced across
  sources to catch a 2-3x price disagreement on one site
- Narrow, honest coverage: history/nature categories only -- activity
  agent falls through to Google Places/mock for anything else

---

### Add Redis-backed caching layer with in-memory fallback
**Date:** August 03, 2026
**Author:** Paarth Agl
**Commit:** a121603

- Redis if REDIS_URL is set and reachable, in-memory otherwise --
  falls back gracefully rather than failing trip planning on cache outage
- Cache keys scoped to search params (route/city/dates), not budget
  ceiling, so reallocation rounds hit cache instead of re-fetching
- 19 tests including real cache-hit verification via respx call counts

---

### Add Docker configs and deployment guide
**Date:** August 03, 2026
**Author:** Paarth Agl
**Commit:** 4c38d82

- Dockerfiles for backend, data service, and frontend (multi-stage w/ nginx)
- docker-compose.yml for one-command local prod-parity testing
- CORS now configurable via CORS_ALLOWED_ORIGINS instead of hardcoded wildcard
- DEPLOYMENT.md: step-by-step Render (backend) + Vercel (frontend) guide

Note: frontend/Dockerfile and nginx.conf ended up in the earlier
frontend commit since those files already existed on disk by the time
this repo was initialized -- logically they belong here.

---

### Add project README, portfolio writeup, and landing page
**Date:** August 03, 2026
**Author:** Paarth Agl
**Commit:** 393eef7

- README ties the whole architecture together with setup instructions
- PORTFOLIO.md: resume bullets, interview talking points, and an
  explicit 'what not to claim' section on data source honesty
- landing/index.html: static showcase page (design via Stitch), fact
  checked against the real project -- corrected several plausible but
  wrong details Stitch invented (wrong tech stack, fabricated dataset
  size, unverified coverage %% replaced with the real measured 92%%)

---
