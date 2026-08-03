# TripSync AI — Frontend

React + TypeScript + Tailwind frontend for the TripSync multi-agent trip planner. Design ported from Stitch (`stitch_tripsync_ai_planner_dashboard` export) — colors, spacing, and type scale in `tailwind.config.js` match `DESIGN.md` exactly.

## Setup

```bash
npm install
cp .env.example .env   # point VITE_API_BASE_URL at your FastAPI backend
npm run dev
```

Backend must be running (see `../api/main.py`) with CORS allowing `http://localhost:5173`.

## Architecture

- **`src/hooks/useTripPlannerSSE.ts`** — the core integration point. POSTs to `/plan-trip`, manually parses the `text/event-stream` response (can't use `EventSource` since it only supports GET), and derives per-agent UI state (`waiting → searching → found/reallocating`) from the `node_complete` events.
- **`src/types/trip.ts`** — mirrors `schemas/messages.py` on the backend. Keep these in sync if the Pydantic schemas change.
- **Screens** map 1:1 to the three Stitch screens:
  - `TripRequestForm` (Screen 1) — client-side validation, interest chips, animated submit button
  - `AgentProgress` (Screen 2) — live agent cards + activity stream timeline, driven entirely by SSE state
  - `ItineraryView` (Screen 3) — Chart.js stacked bar for budget breakdown, best-effort vs within-budget badge
  - `ItineraryLoadingSkeleton` / `PlanningError` — edge states from the design spec

## Known gaps / next steps

- No dark mode toggle wired yet — tokens exist in Stitch's dark export but weren't ported into the Tailwind config.
- Short vs. long trip activity layouts currently both use continuous scroll (per your call) — no pagination/accordion.
- `App.tsx`'s phase state machine is simple (`idle → planning → complete/error`); if you add a "My Trips" history view later, this'll need a router (React Router) instead of local state.
