"""
Unit tests for the pricing/reallocation logic. Pure computation — no
external API mocking needed, which is why this is the first piece
scaffolded.
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from datetime import date, datetime
import pytest

from schemas.messages import (
    TripRequest, FlightOption, HotelOption, ActivitySuggestion,
)
from graph.state import build_initial_state
from graph.pricing_agent import (
    run_pricing_agent, run_reallocation,
    route_after_pricing, route_reallocation_target,
)


def make_request(budget=40000.0):
    return TripRequest(
        destination="Goa",
        origin="Delhi",
        start_date=date(2026, 12, 20),
        end_date=date(2026, 12, 25),
        budget=budget,
        interests=["beaches", "nightlife"],
    )


def make_flight(price=12000.0):
    return FlightOption(
        airline="IndiGo",
        flight_number="6E123",
        departure_time=datetime(2026, 12, 20, 6, 0),
        arrival_time=datetime(2026, 12, 20, 8, 30),
        price=price,
    )


def make_hotel(total_price=20000.0):
    return HotelOption(
        name="Beach Resort",
        area="Baga",
        price_per_night=4000.0,
        total_price=total_price,
    )


def make_activities(total=6000.0):
    return [
        ActivitySuggestion(
            name="Water sports", category="beaches", day=1,
            estimated_cost=total, duration_hours=3,
        )
    ]


class TestBudgetEvaluation:
    def test_under_budget_no_reallocation(self):
        state = build_initial_state(make_request(budget=40000))
        state["flight_result"] = make_flight(12000)
        state["hotel_result"] = make_hotel(18000)
        state["activity_results"] = make_activities(5000)

        result = run_pricing_agent(state)

        assert result["is_over_budget"] is False
        assert result["reallocation_targets"] == []
        assert result["total_cost"] == 35000
        assert result["message_log"][0].status.value == "completed"

    def test_over_budget_flags_worst_variance_category(self):
        state = build_initial_state(make_request(budget=40000))
        # ceilings: flight=16000, hotel=16000, activity=8000
        state["flight_result"] = make_flight(15000)   # under its ceiling
        state["hotel_result"] = make_hotel(22000)      # 6000 over ceiling — worst
        state["activity_results"] = make_activities(9000)  # 1000 over ceiling

        result = run_pricing_agent(state)

        assert result["is_over_budget"] is True
        assert result["reallocation_targets"] == ["hotel"]

    def test_over_budget_but_no_category_exceeds_own_ceiling(self):
        """
        Edge case: total exceeds trip budget even though every category
        is within its own ceiling. Under the initial 40/40/20 split this
        can't happen (ceilings sum exactly to budget by construction),
        but it becomes possible after ceilings have drifted across prior
        reallocation rounds. Should fall back to flagging the largest
        absolute-cost category since nothing individually "violated"
        its ceiling.
        """
        state = build_initial_state(make_request(budget=30000))
        # Simulate drifted ceilings from earlier reallocation rounds — they
        # no longer sum exactly to the trip budget the way the initial
        # 40/40/20 split does by construction.
        state["budget_ceilings"] = {
            "flight": 13000.0,
            "hotel": 13000.0,
            "activity": 7000.0,
        }  # sums to 33000, above the 30000 trip budget
        state["flight_result"] = make_flight(12000)        # within its ceiling
        state["hotel_result"] = make_hotel(12500)            # within its ceiling
        state["activity_results"] = make_activities(6800)  # within its ceiling
        # total = 31300, over the 30000 trip budget, but every category
        # individually sits under its own (drifted) ceiling

        result = run_pricing_agent(state)

        assert result["is_over_budget"] is True
        # Fallback path: largest absolute-cost category (hotel, 12500) flagged
        assert result["reallocation_targets"] == ["hotel"]

    def test_no_hotel_result_yet_treated_as_zero_cost(self):
        state = build_initial_state(make_request(budget=40000))
        state["flight_result"] = make_flight(12000)
        state["hotel_result"] = None
        state["activity_results"] = []

        result = run_pricing_agent(state)

        assert result["total_cost"] == 12000
        assert result["is_over_budget"] is False


class TestReallocation:
    def test_shrinks_only_flagged_category_ceiling(self):
        state = build_initial_state(make_request(budget=40000))
        state["reallocation_targets"] = ["hotel"]
        state["total_cost"] = 44000
        original_flight_ceiling = state["budget_ceilings"]["flight"]
        original_activity_ceiling = state["budget_ceilings"]["activity"]

        result = run_reallocation(state)

        assert result["budget_ceilings"]["flight"] == original_flight_ceiling
        assert result["budget_ceilings"]["activity"] == original_activity_ceiling
        assert result["budget_ceilings"]["hotel"] < state["budget_ceilings"]["hotel"]

    def test_increments_negotiation_round(self):
        state = build_initial_state(make_request(budget=40000))
        state["reallocation_targets"] = ["hotel"]
        state["total_cost"] = 44000
        state["negotiation_round"] = 0

        result = run_reallocation(state)

        assert result["negotiation_round"] == 1

    def test_new_ceiling_never_drops_below_floor(self):
        """Ceiling shouldn't collapse to near-zero even with a huge overage."""
        state = build_initial_state(make_request(budget=40000))
        state["reallocation_targets"] = ["hotel"]
        state["total_cost"] = 200000  # wildly over
        original_ceiling = state["budget_ceilings"]["hotel"]

        result = run_reallocation(state)

        assert result["budget_ceilings"]["hotel"] >= original_ceiling * 0.3


class TestRouting:
    def test_route_synthesize_when_under_budget(self):
        state = build_initial_state(make_request())
        state["is_over_budget"] = False

        assert route_after_pricing(state) == "synthesize"

    def test_route_reallocate_when_over_budget_and_rounds_remain(self):
        state = build_initial_state(make_request())
        state["is_over_budget"] = True
        state["negotiation_round"] = 1
        state["max_negotiation_rounds"] = 3

        assert route_after_pricing(state) == "reallocate"

    def test_route_synthesize_when_max_rounds_hit_even_if_over_budget(self):
        state = build_initial_state(make_request())
        state["is_over_budget"] = True
        state["negotiation_round"] = 3
        state["max_negotiation_rounds"] = 3

        assert route_after_pricing(state) == "synthesize"

    @pytest.mark.parametrize("category,expected_node", [
        ("flight", "flight_agent"),
        ("hotel", "hotel_agent"),
        ("activity", "activity_agent"),
    ])
    def test_route_reallocation_target_maps_category_to_node(self, category, expected_node):
        state = build_initial_state(make_request())
        state["reallocation_targets"] = [category]

        assert route_reallocation_target(state) == expected_node


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
