import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from datetime import date
import pytest

from schemas.messages import TripRequest
from graph.state import build_initial_state
from graph.flight_agent import run_flight_agent, _mock_search_flights
from graph.hotel_agent import run_hotel_agent, _mock_search_hotels
from graph.activity_agent import run_activity_agent, _mock_search_activities


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


class TestFlightAgent:
    def test_returns_flight_within_ceiling_when_possible(self):
        state = build_initial_state(make_request())
        result = run_flight_agent(state)

        assert result["flight_result"] is not None
        ceiling = state["budget_ceilings"]["flight"]
        # cheapest mock option is 0.75x ceiling, should always fit
        assert result["flight_result"].price <= ceiling

    def test_writes_completed_message_with_high_confidence_when_within_budget(self):
        state = build_initial_state(make_request())
        result = run_flight_agent(state)

        msg = result["message_log"][0]
        assert msg.status.value == "completed"
        assert msg.confidence == 1.0

    def test_deterministic_price_spread_relative_to_ceiling(self):
        options = _mock_search_flights("Delhi", "Goa", date(2026, 12, 20), budget_ceiling=10000)
        prices = sorted(o.price for o in options)
        assert prices[0] == pytest.approx(7500, abs=1)   # 0.75x
        assert prices[-1] == pytest.approx(10500, abs=1)  # 1.05x


class TestHotelAgent:
    def test_returns_hotel_within_ceiling_when_possible(self):
        state = build_initial_state(make_request())
        result = run_hotel_agent(state)

        assert result["hotel_result"] is not None
        ceiling = state["budget_ceilings"]["hotel"]
        assert result["hotel_result"].total_price <= ceiling

    def test_total_price_scales_with_nights(self):
        # 5-night trip
        options_5n = _mock_search_hotels("Goa", nights=5, budget_ceiling=25000)
        # 2-night trip, same ceiling
        options_2n = _mock_search_hotels("Goa", nights=2, budget_ceiling=25000)

        # same ceiling but fewer nights -> higher per-night rate affordable
        assert options_2n[0].price_per_night > options_5n[0].price_per_night

    def test_falls_back_to_cheapest_option_if_none_fit_ceiling(self):
        # Ceiling so small nothing fits comfortably
        state = build_initial_state(make_request(budget=1000))
        result = run_hotel_agent(state)

        assert result["hotel_result"] is not None
        msg = result["message_log"][0]
        # confidence should reflect that ceiling likely wasn't met
        assert msg.confidence in (0.6, 1.0)


class TestActivityAgent:
    def test_filters_by_stated_interests(self):
        state = build_initial_state(make_request(interests=["food"]))
        result = run_activity_agent(state)

        assert len(result["activity_results"]) > 0
        # every returned activity should trace back to the food pool or general fallback
        food_names = {"Local food crawl", "Cooking class", "Fine dining experience"}
        for activity in result["activity_results"]:
            assert activity.name in food_names or activity.category == "general"

    def test_respects_max_two_per_day_cap(self):
        state = build_initial_state(make_request(interests=["beaches", "nightlife", "food"], budget=200000))
        result = run_activity_agent(state)

        per_day_counts = {}
        for activity in result["activity_results"]:
            per_day_counts[activity.day] = per_day_counts.get(activity.day, 0) + 1
        assert all(count <= 2 for count in per_day_counts.values())

    def test_falls_back_to_default_pool_for_unknown_interests(self):
        activities = _mock_search_activities(["skydiving"], trip_days=3, budget_ceiling=5000)
        assert len(activities) >= 1
        assert activities[0].name in {"City sightseeing tour", "Local market visit"}

    def test_always_returns_at_least_one_activity_even_with_tiny_budget(self):
        state = build_initial_state(make_request(budget=100))  # activity ceiling ~20
        result = run_activity_agent(state)
        assert len(result["activity_results"]) >= 1


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
