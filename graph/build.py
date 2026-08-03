"""
Assembles the AI Travel Planner's LangGraph StateGraph.

Structure:
  START --> flight_agent   --\
        --> hotel_agent      --> pricing_agent --(over budget)--> reallocate --> [flagged agent] --> pricing_agent (loop)
        --> activity_agent  --/                 --(within budget or rounds exhausted)--> synthesize --> END

flight_agent, hotel_agent, activity_agent run in parallel on the initial
fan-out from START. pricing_agent is a fan-in join: LangGraph won't run
it until all three parallel predecessors have completed. On a
reallocation round, only the single flagged agent is re-invoked before
looping back into pricing_agent — the other two results are left
untouched in state.
"""
from langgraph.graph import StateGraph, START, END

from graph.state import TravelPlannerState
from graph.flight_agent import run_flight_agent
from graph.hotel_agent import run_hotel_agent
from graph.activity_agent import run_activity_agent
from graph.pricing_agent import (
    run_pricing_agent, run_reallocation,
    route_after_pricing, route_reallocation_target,
)
from graph.synthesis import run_synthesis


def build_travel_planner_graph():
    graph = StateGraph(TravelPlannerState)

    graph.add_node("flight_agent", run_flight_agent)
    graph.add_node("hotel_agent", run_hotel_agent)
    graph.add_node("activity_agent", run_activity_agent)
    graph.add_node("pricing_agent", run_pricing_agent)
    graph.add_node("reallocate", run_reallocation)
    graph.add_node("synthesize", run_synthesis)

    # Fan-out: all three domain agents run in parallel from START
    graph.add_edge(START, "flight_agent")
    graph.add_edge(START, "hotel_agent")
    graph.add_edge(START, "activity_agent")

    # Fan-in: pricing_agent waits for all three before running
    graph.add_edge("flight_agent", "pricing_agent")
    graph.add_edge("hotel_agent", "pricing_agent")
    graph.add_edge("activity_agent", "pricing_agent")

    # After pricing: either synthesize (done / gave up) or reallocate
    graph.add_conditional_edges(
        "pricing_agent",
        route_after_pricing,
        {"synthesize": "synthesize", "reallocate": "reallocate"},
    )

    # After reallocate: route to whichever single agent was flagged.
    # These target the same three node names already wired above, so
    # each flagged agent's output re-feeds into pricing_agent via the
    # fan-in edges already declared — no new edges needed for the loop.
    graph.add_conditional_edges(
        "reallocate",
        route_reallocation_target,
        {
            "flight_agent": "flight_agent",
            "hotel_agent": "hotel_agent",
            "activity_agent": "activity_agent",
        },
    )

    graph.add_edge("synthesize", END)

    return graph.compile()


# Module-level compiled graph, ready to invoke.
travel_planner_graph = build_travel_planner_graph()
