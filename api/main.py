"""
FastAPI layer exposing the travel planner graph over HTTP.

POST /plan-trip streams progress via Server-Sent Events as the graph
executes — one event per node completion (flight_agent, hotel_agent,
activity_agent, pricing_agent, reallocate, synthesize), so a frontend
can render "Flight found ✓ / Checking budget... / Reallocating hotel
budget..." live instead of waiting on one big blocking response.
"""
import json
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import ValidationError

from config import settings
from schemas.messages import TripRequest
from graph.state import build_initial_state
from graph.build import build_travel_planner_graph

app = FastAPI(title="AI Travel Planner", version="0.1.0")

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
                yield _sse_event("node_complete", {
                    "node": node_name,
                    "status": update.get("status"),
                    "is_over_budget": update.get("is_over_budget"),
                    "negotiation_round": update.get("negotiation_round"),
                })

                if node_name == "synthesize" and update.get("final_itinerary"):
                    yield _sse_event("itinerary_ready", update["final_itinerary"])

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


@app.get("/health")
async def health():
    return {"status": "ok"}
