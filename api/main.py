"""
FastAPI layer exposing the travel planner graph over HTTP.

POST /plan-trip streams progress via Server-Sent Events as the graph
executes — one event per node completion (flight_agent, hotel_agent,
activity_agent, pricing_agent, reallocate, synthesize), so a frontend
can render "Flight found ✓ / Checking budget... / Reallocating hotel
budget..." live instead of waiting on one big blocking response.
"""
import json
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import ValidationError

from config import settings
from schemas.messages import TripRequest
from graph.state import build_initial_state
from graph.build import build_travel_planner_graph
from storage import ItineraryStore

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.cors_is_wildcard:
        logger.warning("CORS is set to '*' (allow all origins). Set CORS_ALLOWED_ORIGINS in .env before deploying.")
    if not settings.redis_url:
        logger.warning("Using in-memory cache (not shared across workers). Set REDIS_URL for multi-worker deployments.")
    yield


app = FastAPI(title="AI Travel Planner", version="0.1.0", lifespan=lifespan)

# CORS_ALLOWED_ORIGINS in .env: comma-separated list, e.g.
# "https://tripsync.vercel.app,http://localhost:5173". Defaults to "*"
# for local dev — set this explicitly before deploying anywhere real.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins_list,
    allow_methods=["*"],
    allow_headers=["*"],
)

_graph = build_travel_planner_graph()
_store = ItineraryStore()


def _sse_event(event: str, data: dict) -> str:
    """Formats a single SSE frame."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


async def _stream_trip_plan(request: TripRequest, max_negotiation_rounds: int) -> AsyncGenerator[str, None]:
    initial_state = build_initial_state(request, max_negotiation_rounds=max_negotiation_rounds)

    try:
        # stream_mode="updates" yields {node_name: partial_state_update}
        # after each node completes — exactly the granularity we want
        # for progress events.
        for step in _graph.stream(initial_state, stream_mode="updates"):
            for node_name, update in step.items():
                # Each node returns its own AgentMessage(s) in message_log
                # (merged into the accumulated log via the operator.add
                # reducer) — pull data_source from the most recent one so
                # the frontend can show whether this result came from the
                # own data service, a third-party API, or mock fallback.
                node_messages = update.get("message_log", [])
                data_source = node_messages[-1].payload.get("data_source") if node_messages else None

                yield _sse_event("node_complete", {
                    "node": node_name,
                    "status": update.get("status"),
                    "is_over_budget": update.get("is_over_budget"),
                    "negotiation_round": update.get("negotiation_round"),
                    "data_source": data_source,
                })

                if node_name == "synthesize" and update.get("final_itinerary"):
                    final_itinerary = update["final_itinerary"]
                    trip_id = _store.save(final_itinerary)
                    final_itinerary["id"] = trip_id
                    yield _sse_event("itinerary_ready", final_itinerary)

    except Exception as exc:
        yield _sse_event("error", {"message": str(exc)})
        return

    yield _sse_event("done", {})


@app.post("/plan-trip")
async def plan_trip(request: dict):
    try:
        trip_request = TripRequest(**{k: v for k, v in request.items() if k != "max_negotiation_rounds"})
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors())

    max_rounds = request.get("max_negotiation_rounds", 3)

    return StreamingResponse(
        _stream_trip_plan(trip_request, max_rounds),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # disable nginx buffering for SSE
        },
    )


@app.get("/trips")
async def list_trips():
    return _store.list_all()


@app.get("/trips/{trip_id}")
async def get_trip(trip_id: str):
    trip = _store.get(trip_id)
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    return trip


@app.delete("/trips/{trip_id}")
async def delete_trip(trip_id: str):
    if not _store.delete(trip_id):
        raise HTTPException(status_code=404, detail="Trip not found")
    return {"status": "deleted"}


@app.get("/health")
async def health():
    return {"status": "ok"}

