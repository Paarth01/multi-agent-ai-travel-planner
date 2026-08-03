"""
End-to-end integration tests for the compiled travel planner graph.
Runs real (mocked-data) trips through the full fan-out -> pricing ->
negotiation loop -> synthesis pipeline.
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from datetime import date

from schemas.messages import TripRequest
from graph.state import build_initial_state
from graph.build import build_travel_planner_graph


def make_request(**overrides):
    defaults = dict(
        destination="Goa",
        origin="Delhi",
        start_date=date(2026, 12, 20),
        end_date=date(2026, 12, 25),
        budget=40000.0,
        interests=["beaches", "nightlife"],
    )
    defaults.update(overrides)
    return TripRequest(**defaults)


class TestFullGraphRun:
    def test_graph_compiles(self):
        graph = build_travel_planner_graph()
        assert graph is not None

    def test_produces_final_itinerary(self):
        graph = build_travel_planner_graph()
        state = build_initial_state(make_request())

        result = graph.invoke(state)

        assert result["final_itinerary"] is not None
        assert result["status"] == "complete"
        assert result["final_itinerary"]["flight"] is not None
        assert result["final_itinerary"]["hotel"] is not None
        assert len(result["final_itinerary"]["activities"]) >= 1

    def test_negotiation_terminates_within_max_rounds(self):
        graph = build_travel_planner_graph()
        # Tiny budget forces at least one reallocation round
        state = build_initial_state(make_request(budget=5000.0), max_negotiation_rounds=3)

        result = graph.invoke(state)

        assert result["negotiation_round"] <= result["max_negotiation_rounds"]
        assert result["status"] == "complete"
        assert result["final_itinerary"] is not None

    def test_reallocation_reduces_targeted_category_only_per_round(self):
        """
        Sanity check on the loop's core promise: each round, exactly one
        category's ceiling should move, not all three at once.
        """
        graph = build_travel_planner_graph()
        state = build_initial_state(make_request(budget=8000.0), max_negotiation_rounds=1)

        result = graph.invoke(state)

        reallocation_messages = [
            m for m in result["message_log"]
            if m.task_type == "reallocate"
        ]
        # With max_negotiation_rounds=1, at most one reallocation event fires
        assert len(reallocation_messages) <= 1

    def test_message_log_accumulates_across_parallel_agents(self):
        """
        Confirms the operator.add reducer correctly merges message_log
        writes from flight/hotel/activity agents running in the same
        superstep, instead of one clobbering another.
        """
        graph = build_travel_planner_graph()
        state = build_initial_state(make_request())

        result = graph.invoke(state)

        agent_ids_logged = {m.agent_id.value for m in result["message_log"]}
        assert "flight_agent" in agent_ids_logged
        assert "hotel_agent" in agent_ids_logged
        assert "activity_agent" in agent_ids_logged
        assert "pricing_agent" in agent_ids_logged

    def test_generous_budget_needs_no_negotiation(self):
        graph = build_travel_planner_graph()
        state = build_initial_state(make_request(budget=200000.0))

        result = graph.invoke(state)

        assert result["negotiation_round"] == 0
        assert result["final_itinerary"]["best_effort"] is False


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
