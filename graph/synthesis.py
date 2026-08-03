"""
Synthesis node — final step of the graph. Assembles the Itinerary
schema from whatever the agents landed on, whether or not the
negotiation loop resolved within budget.
"""
from schemas.messages import AgentMessage, AgentID, TaskStatus, Itinerary
from graph.pricing_agent import compute_budget_breakdown
from graph.state import TravelPlannerState


def run_synthesis(state: TravelPlannerState) -> dict:
    breakdown = compute_budget_breakdown(state)
    best_effort = state["is_over_budget"]  # still over budget when we stopped negotiating

    itinerary = Itinerary(
        trip_request=state["request"],
        flight=state["flight_result"],
        hotel=state["hotel_result"],
        activities=state["activity_results"],
        budget_breakdown=breakdown,
        total_cost=state["total_cost"],
        negotiation_rounds=state["negotiation_round"],
        best_effort=best_effort,
    )

    message = AgentMessage(
        agent_id=AgentID.ORCHESTRATOR,
        task_type="synthesize_itinerary",
        status=TaskStatus.COMPLETED,
        payload={"best_effort": best_effort, "negotiation_rounds": state["negotiation_round"]},
    )

    return {
        "final_itinerary": itinerary.model_dump(mode="json"),
        "status": "complete",
        "message_log": [message],
    }
