"""
Shared LangGraph state for the AI Travel Planner.

All agents read from and write to this single state object. Agents never
call each other directly — coordination happens entirely through state
mutations mediated by the orchestrator graph.
"""
from typing import TypedDict, Annotated, Optional
import operator

from schemas.messages import (
    AgentMessage, FlightOption, HotelOption,
    ActivitySuggestion, TripRequest,
)


class TravelPlannerState(TypedDict):
    # Input — set once at graph invocation, never mutated after
    request: TripRequest

    # Per-category budget ceilings — mutable; reallocation adjusts these
    budget_ceilings: dict[str, float]  # {"flight": 15000, "hotel": 18000, "activity": 7000}

    # Agent outputs — each agent writes only to its own key
    flight_result: Optional[FlightOption]
    hotel_result: Optional[HotelOption]
    activity_results: list[ActivitySuggestion]

    # Append-only audit log. operator.add reducer merges parallel writes
    # instead of letting concurrent fan-out nodes clobber each other.
    message_log: Annotated[list[AgentMessage], operator.add]

    # Pricing agent's running assessment
    total_cost: float
    is_over_budget: bool
    reallocation_targets: list[str]   # e.g. ["hotel"] — category names, not agent IDs
    negotiation_round: int
    max_negotiation_rounds: int

    # Terminal output
    final_itinerary: Optional[dict]
    status: str  # "planning" | "negotiating" | "complete" | "failed"


def build_initial_state(request: TripRequest, max_negotiation_rounds: int = 3) -> TravelPlannerState:
    """
    Constructs the starting state for a graph run. Splits the total budget
    into initial per-category ceilings using a simple fixed ratio; agents
    can be given more sophisticated initial splitting logic later without
    changing the state shape.
    """
    flight_ceiling = round(request.budget * 0.40, 2)
    hotel_ceiling = round(request.budget * 0.40, 2)
    activity_ceiling = round(request.budget * 0.20, 2)

    return TravelPlannerState(
        request=request,
        budget_ceilings={
            "flight": flight_ceiling,
            "hotel": hotel_ceiling,
            "activity": activity_ceiling,
        },
        flight_result=None,
        hotel_result=None,
        activity_results=[],
        message_log=[],
        total_cost=0.0,
        is_over_budget=False,
        reallocation_targets=[],
        negotiation_round=0,
        max_negotiation_rounds=max_negotiation_rounds,
        final_itinerary=None,
        status="planning",
    )
