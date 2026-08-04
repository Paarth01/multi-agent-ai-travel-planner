import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import json
from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def parse_sse_events(raw_text: str) -> list[dict]:
    """Splits raw SSE stream text into [{event, data}] dicts."""
    events = []
    for block in raw_text.strip().split("\n\n"):
        if not block.strip():
            continue
        event_line, data_line = None, None
        for line in block.split("\n"):
            if line.startswith("event:"):
                event_line = line.removeprefix("event:").strip()
            elif line.startswith("data:"):
                data_line = line.removeprefix("data:").strip()
        if event_line and data_line is not None:
            events.append({"event": event_line, "data": json.loads(data_line)})
    return events


class TestHealthCheck:
    def test_health_endpoint(self):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestPlanTripEndpoint:
    def _valid_payload(self, **overrides):
        payload = {
            "destination": "Goa",
            "origin": "Delhi",
            "start_date": "2026-12-20",
            "end_date": "2026-12-25",
            "budget": 40000.0,
            "interests": ["beaches", "nightlife"],
        }
        payload.update(overrides)
        return payload

    def test_returns_422_on_invalid_payload(self):
        response = client.post("/plan-trip", json={"destination": "Goa"})  # missing required fields
        assert response.status_code == 422

    def test_streams_node_complete_events_for_all_domain_agents(self):
        response = client.post("/plan-trip", json=self._valid_payload())
        assert response.status_code == 200

        events = parse_sse_events(response.text)
        node_names = {e["data"]["node"] for e in events if e["event"] == "node_complete"}

        assert "flight_agent" in node_names
        assert "hotel_agent" in node_names
        assert "activity_agent" in node_names
        assert "pricing_agent" in node_names

    def test_ends_with_itinerary_ready_then_done(self):
        response = client.post("/plan-trip", json=self._valid_payload())
        events = parse_sse_events(response.text)

        event_types = [e["event"] for e in events]
        assert "itinerary_ready" in event_types
        assert event_types[-1] == "done"
        # itinerary_ready must come before done
        assert event_types.index("itinerary_ready") < event_types.index("done")

    def test_itinerary_ready_payload_has_expected_shape(self):
        response = client.post("/plan-trip", json=self._valid_payload())
        events = parse_sse_events(response.text)

        itinerary_event = next(e for e in events if e["event"] == "itinerary_ready")
        data = itinerary_event["data"]

        assert "flight" in data
        assert "hotel" in data
        assert "activities" in data
        assert "budget_breakdown" in data

    def test_tiny_budget_triggers_reallocate_node(self, monkeypatch):
        """
        The mock price generators scale proportionally to each category's
        ceiling, so shrinking the overall budget alone rarely forces an
        overage (cheapest options are chosen below their ceiling by
        design). To reliably exercise the reallocation branch, force one
        agent's mock data to return an option that's guaranteed to blow
        the budget, regardless of ceiling size.
        """
        import graph.flight_agent as flight_agent_module
        from schemas.messages import FlightOption
        from datetime import datetime

        def _expensive_flight(*args, **kwargs):
            return [FlightOption(
                airline="Vistara", flight_number="UK999",
                departure_time=datetime(2026, 12, 20, 6, 0),
                arrival_time=datetime(2026, 12, 20, 9, 0),
                price=999999.0,  # deliberately absurd, guaranteed over any budget
            )]

        monkeypatch.setattr(flight_agent_module, "_mock_search_flights", _expensive_flight)

        response = client.post("/plan-trip", json=self._valid_payload(budget=40000.0))
        events = parse_sse_events(response.text)

        node_names = [e["data"]["node"] for e in events if e["event"] == "node_complete"]
        assert "reallocate" in node_names

    def test_custom_max_negotiation_rounds_is_respected(self):
        response = client.post("/plan-trip", json=self._valid_payload(budget=1000.0, max_negotiation_rounds=1))
        events = parse_sse_events(response.text)

        reallocate_events = [
            e for e in events
            if e["event"] == "node_complete" and e["data"]["node"] == "reallocate"
        ]
        assert len(reallocate_events) <= 1


    def test_node_complete_events_include_data_source(self):
        """
        Regression test for a real gap found during deployment: node_complete
        events originally omitted data_source entirely, so there was no way
        to tell from the API response whether a result came from the own
        data service, a third-party API, or mock fallback.
        """
        response = client.post("/plan-trip", json=self._valid_payload())
        events = parse_sse_events(response.text)

        node_events = [e for e in events if e["event"] == "node_complete"]
        domain_agent_events = [e for e in node_events if e["data"]["node"] in ("flight_agent", "hotel_agent", "activity_agent")]

        assert len(domain_agent_events) == 3
        for event in domain_agent_events:
            assert event["data"]["data_source"] in ("own_service", "amadeus", "google_places", "mock")


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
