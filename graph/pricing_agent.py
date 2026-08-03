"""
Pricing Agent — pure computation, no external API calls.

Responsibilities:
1. Evaluate the combined cost of current flight/hotel/activity picks
   against the trip's total budget.
2. If over budget, flag exactly one category for reallocation: the one
   with the largest variance (actual - allocated), since that's the
   biggest lever to pull.
3. Emit an AgentMessage documenting the evaluation for the audit log.
"""
from schemas.messages import AgentMessage, AgentID, TaskStatus, BudgetLine
from graph.state import TravelPlannerState


def compute_budget_breakdown(state: TravelPlannerState) -> list[BudgetLine]:
    ceilings = state["budget_ceilings"]

    flight_actual = state["flight_result"].price if state["flight_result"] else 0.0
    hotel_actual = state["hotel_result"].total_price if state["hotel_result"] else 0.0
    activity_actual = sum(a.estimated_cost for a in state["activity_results"])

    return [
        BudgetLine(category="flight", allocated=ceilings["flight"], actual=flight_actual),
        BudgetLine(category="hotel", allocated=ceilings["hotel"], actual=hotel_actual),
        BudgetLine(category="activity", allocated=ceilings["activity"], actual=activity_actual),
    ]


def run_pricing_agent(state: TravelPlannerState) -> dict:
    breakdown = compute_budget_breakdown(state)
    total = sum(line.actual for line in breakdown)
    over_budget = total > state["request"].budget

    reallocation_targets: list[str] = []
    if over_budget:
        # Pick the single worst offender by variance (actual - allocated).
        # Ties broken by category order: flight, hotel, activity.
        worst = max(breakdown, key=lambda line: line.variance)
        # Only flag it if it's actually over its own ceiling — if the
        # overall total is over budget but every category individually
        # is within its ceiling, that means ceilings themselves were set
        # too generously relative to total budget. Flag the largest
        # absolute-cost category instead so reallocation has something to shrink.
        if worst.variance > 0:
            reallocation_targets = [worst.category]
        else:
            largest_cost = max(breakdown, key=lambda line: line.actual)
            reallocation_targets = [largest_cost.category]

    message = AgentMessage(
        agent_id=AgentID.PRICING,
        task_type="evaluate_budget",
        status=TaskStatus.NEEDS_REALLOCATION if over_budget else TaskStatus.COMPLETED,
        payload={
            "total_cost": total,
            "budget": state["request"].budget,
            "breakdown": [line.model_dump() for line in breakdown],
            "reallocation_targets": reallocation_targets,
        },
    )

    return {
        "total_cost": total,
        "is_over_budget": over_budget,
        "reallocation_targets": reallocation_targets,
        "message_log": [message],
    }


def run_reallocation(state: TravelPlannerState) -> dict:
    """
    Shrinks the ceiling for the flagged category and increments the
    negotiation round counter. Shrink amount: enough to bring the
    overall total back within budget, applied only to the flagged
    category, with a 10% safety margin so a single round is more
    likely to resolve it.
    """
    if not state["reallocation_targets"]:
        # Nothing to do — shouldn't normally be reached because the
        # graph's conditional edge only routes here when targets exist.
        return {"negotiation_round": state["negotiation_round"] + 1}

    category = state["reallocation_targets"][0]
    overage = state["total_cost"] - state["request"].budget
    current_ceiling = state["budget_ceilings"][category]

    # Reduce the flagged category's ceiling by the overage plus a 10%
    # margin, but never below a small floor so the agent still has
    # something workable to search with.
    new_ceiling = max(current_ceiling - overage * 1.10, current_ceiling * 0.3)

    updated_ceilings = dict(state["budget_ceilings"])
    updated_ceilings[category] = round(new_ceiling, 2)

    message = AgentMessage(
        agent_id=AgentID.PRICING,
        task_type="reallocate",
        status=TaskStatus.IN_PROGRESS,
        payload={
            "category": category,
            "old_ceiling": current_ceiling,
            "new_ceiling": updated_ceilings[category],
            "overage": overage,
        },
    )

    return {
        "budget_ceilings": updated_ceilings,
        "negotiation_round": state["negotiation_round"] + 1,
        "message_log": [message],
    }


def route_after_pricing(state: TravelPlannerState) -> str:
    if not state["is_over_budget"]:
        return "synthesize"
    if state["negotiation_round"] >= state["max_negotiation_rounds"]:
        return "synthesize"  # give up gracefully, ship best-effort itinerary
    return "reallocate"


def route_reallocation_target(state: TravelPlannerState) -> str:
    """
    Maps the flagged budget category to the LangGraph node name that
    should be re-invoked.
    """
    category_to_node = {
        "flight": "flight_agent",
        "hotel": "hotel_agent",
        "activity": "activity_agent",
    }
    category = state["reallocation_targets"][0]
    return category_to_node[category]
