"""
Pricing Agent — pure computation, no external API calls.

Responsibilities:
1. Evaluate the combined cost of current flight/hotel/activity picks
   against the trip's total budget.
2. If over budget, flag exactly one category for reallocation: the one
   with the largest variance (actual - allocated), preferring
   categories that aren't already "at floor" (see _floor_flags below)
   since reallocating a floored category is a guaranteed no-op.
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


def _floor_flags(state: TravelPlannerState) -> dict[str, bool]:
    """
    Per-category "already at its real/live cheapest option" flags, set
    by each domain agent. Real data sources (own service, Amadeus)
    don't accept a price ceiling as a search parameter, so re-querying
    after a ceiling shrink can return the exact same result — these
    flags let the pricing agent recognize a category has no cheaper
    option to find, rather than burning negotiation rounds on it.
    Defaults to False for any state that predates these fields (e.g.
    states built without agents having run yet).
    """
    return {
        "flight": state.get("flight_at_floor", False),
        "hotel": state.get("hotel_at_floor", False),
        "activity": state.get("activity_at_floor", False),
    }


def run_pricing_agent(state: TravelPlannerState) -> dict:
    breakdown = compute_budget_breakdown(state)
    total = sum(line.actual for line in breakdown)
    over_budget = total > state["request"].budget

    reallocation_targets: list[str] = []
    if over_budget:
        floor_flags = _floor_flags(state)
        over_ceiling_lines = [line for line in breakdown if line.variance > 0]

        if over_ceiling_lines:
            # Prefer a category that isn't already at its floor — only
            # fall back to a floored category if every over-ceiling
            # category is floored (nothing better to target).
            non_floor_candidates = [line for line in over_ceiling_lines if not floor_flags.get(line.category, False)]
            candidates = non_floor_candidates or over_ceiling_lines
            worst = max(candidates, key=lambda line: line.variance)
            reallocation_targets = [worst.category]
        else:
            # Total over budget but nothing individually over its own
            # ceiling — ceilings have drifted (see build_initial_state's
            # 40/40/20 split not summing to budget after prior rounds).
            # Flag the largest absolute-cost category, same floor
            # preference as above.
            non_floor_all = [line for line in breakdown if not floor_flags.get(line.category, False)]
            candidates = non_floor_all or breakdown
            largest_cost = max(candidates, key=lambda line: line.actual)
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

    # If every category currently over its ceiling is already at its
    # real/live floor, further reallocation rounds are guaranteed
    # no-ops — there's no cheaper option left to find. Stop early
    # rather than burning rounds and duplicate network calls for a
    # result that can't change. (Categories with real fixed data, e.g.
    # activities backed by hand-curated ASI fees, are floored by
    # definition — there's only ever one real price.)
    breakdown = compute_budget_breakdown(state)
    over_ceiling_categories = [line.category for line in breakdown if line.variance > 0]
    if over_ceiling_categories:
        floor_flags = _floor_flags(state)
        if all(floor_flags.get(c, False) for c in over_ceiling_categories):
            return "synthesize"

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
