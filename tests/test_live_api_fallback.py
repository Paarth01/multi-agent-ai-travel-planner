import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from datetime import date, datetime
from unittest.mock import MagicMock

import pytest

from schemas.messages import TripRequest, FlightOption, HotelOption
from graph.state import build_initial_state
from clients.amadeus_client import AmadeusAPIError
from clients.google_places_client import GooglePlacesAPIError

import graph.flight_agent as flight_agent_module
import graph.hotel_agent as hotel_agent_module
import graph.activity_agent as activity_agent_module
from config import settings


def make_request(**overrides):
    defaults = dict(
        destination="Goa",
        origin="Delhi",
        start_date=date(2026, 12, 20),
        end_date=date(2026, 12, 25),
        budget=40000.0,
        interests=["beaches"],
    )
    defaults.update(overrides)
    return TripRequest(**defaults)


@pytest.fixture
def amadeus_configured(monkeypatch):
    monkeypatch.setattr(settings, "amadeus_client_id", "fake-id")
    monkeypatch.setattr(settings, "amadeus_client_secret", "fake-secret")
    yield


@pytest.fixture
def google_places_configured(monkeypatch):
    monkeypatch.setattr(settings, "google_places_api_key", "fake-key")
    yield


class TestFlightAgentFallback:
    def test_uses_mock_when_not_configured(self):
        assert settings.amadeus_configured is False  # sanity check for test isolation
        state = build_initial_state(make_request())
        result = flight_agent_module.run_flight_agent(state)
        assert result["message_log"][0].payload["data_source"] == "mock"

    def test_uses_live_data_when_configured_and_successful(self, amadeus_configured, monkeypatch):
        fake_client = MagicMock()
        fake_client.resolve_city_code.side_effect = ["DEL", "GOI"]
        fake_client.search_flights.return_value = [
            {
                "price": {"total": "5400.00"},
                "itineraries": [{
                    "segments": [{
                        "carrierCode": "6E", "number": "543",
                        "departure": {"at": "2026-12-20T06:00:00"},
                        "arrival": {"at": "2026-12-20T08:30:00"},
                    }]
                }],
            }
        ]
        monkeypatch.setattr(flight_agent_module, "_get_amadeus_client", lambda: fake_client)

        state = build_initial_state(make_request())
        result = flight_agent_module.run_flight_agent(state)

        assert result["message_log"][0].payload["data_source"] == "amadeus"
        assert result["flight_result"].price == 5400.0
        assert result["flight_result"].airline == "IndiGo"  # mapped from carrier code 6E

    def test_falls_back_to_mock_when_live_search_raises(self, amadeus_configured, monkeypatch):
        fake_client = MagicMock()
        fake_client.resolve_city_code.side_effect = AmadeusAPIError("city not found")
        monkeypatch.setattr(flight_agent_module, "_get_amadeus_client", lambda: fake_client)

        state = build_initial_state(make_request())
        result = flight_agent_module.run_flight_agent(state)

        assert result["message_log"][0].payload["data_source"] == "mock"
        assert result["flight_result"] is not None  # still produced a usable result

    def test_falls_back_to_mock_when_live_search_returns_empty(self, amadeus_configured, monkeypatch):
        fake_client = MagicMock()
        fake_client.resolve_city_code.side_effect = ["DEL", "GOI"]
        fake_client.search_flights.return_value = []
        monkeypatch.setattr(flight_agent_module, "_get_amadeus_client", lambda: fake_client)

        state = build_initial_state(make_request())
        result = flight_agent_module.run_flight_agent(state)

        assert result["message_log"][0].payload["data_source"] == "mock"


class TestFlightAgentOwnServiceTier:
    def test_uses_own_service_when_configured_and_successful(self, monkeypatch):
        monkeypatch.setattr(settings, "own_flight_service_url", "http://localhost:8100")
        fake_client = MagicMock()
        fake_client.search_flights.return_value = [
            {
                "airline": "IndiGo",
                "flight_number": "6E543",
                "departure_time": "2026-12-20T06:00:00",
                "arrival_time": "2026-12-20T08:30:00",
                "price": 4800.0,
                "stops": 0,
            }
        ]
        monkeypatch.setattr(flight_agent_module, "_get_own_data_client", lambda: fake_client)

        state = build_initial_state(make_request())
        result = flight_agent_module.run_flight_agent(state)

        assert result["message_log"][0].payload["data_source"] == "own_service"
        assert result["flight_result"].price == 4800.0

    def test_own_service_takes_priority_over_amadeus_when_both_configured(
        self, amadeus_configured, monkeypatch
    ):
        monkeypatch.setattr(settings, "own_flight_service_url", "http://localhost:8100")
        own_client = MagicMock()
        own_client.search_flights.return_value = [
            {
                "airline": "IndiGo", "flight_number": "6E001",
                "departure_time": "2026-12-20T06:00:00", "arrival_time": "2026-12-20T08:00:00",
                "price": 3000.0, "stops": 0,
            }
        ]
        amadeus_client = MagicMock()  # should never be called
        monkeypatch.setattr(flight_agent_module, "_get_own_data_client", lambda: own_client)
        monkeypatch.setattr(flight_agent_module, "_get_amadeus_client", lambda: amadeus_client)

        state = build_initial_state(make_request())
        result = flight_agent_module.run_flight_agent(state)

        assert result["message_log"][0].payload["data_source"] == "own_service"
        amadeus_client.resolve_city_code.assert_not_called()

    def test_falls_through_to_amadeus_when_own_service_has_no_coverage(
        self, amadeus_configured, monkeypatch
    ):
        monkeypatch.setattr(settings, "own_flight_service_url", "http://localhost:8100")
        own_client = MagicMock()
        own_client.search_flights.side_effect = flight_agent_module.OwnDataServiceError("no coverage for this route")
        amadeus_client = MagicMock()
        amadeus_client.resolve_city_code.side_effect = ["XXX", "YYY"]
        amadeus_client.search_flights.return_value = [
            {
                "price": {"total": "9000.00"},
                "itineraries": [{"segments": [{
                    "carrierCode": "AI", "number": "202",
                    "departure": {"at": "2026-12-20T09:00:00"},
                    "arrival": {"at": "2026-12-20T11:00:00"},
                }]}],
            }
        ]
        monkeypatch.setattr(flight_agent_module, "_get_own_data_client", lambda: own_client)
        monkeypatch.setattr(flight_agent_module, "_get_amadeus_client", lambda: amadeus_client)

        state = build_initial_state(make_request())
        result = flight_agent_module.run_flight_agent(state)

        assert result["message_log"][0].payload["data_source"] == "amadeus"

    def test_falls_through_to_mock_when_neither_live_source_available(self, monkeypatch):
        monkeypatch.setattr(settings, "own_flight_service_url", "http://localhost:8100")
        own_client = MagicMock()
        own_client.search_flights.side_effect = flight_agent_module.OwnDataServiceError("service down")
        monkeypatch.setattr(flight_agent_module, "_get_own_data_client", lambda: own_client)
        # Amadeus not configured in this test

        state = build_initial_state(make_request())
        result = flight_agent_module.run_flight_agent(state)

        assert result["message_log"][0].payload["data_source"] == "mock"
        assert result["flight_result"] is not None


class TestHotelAgentFallback:
    def test_uses_mock_when_not_configured(self):
        state = build_initial_state(make_request())
        result = hotel_agent_module.run_hotel_agent(state)
        assert result["message_log"][0].payload["data_source"] == "mock"

    def test_uses_live_data_when_configured_and_successful(self, amadeus_configured, monkeypatch):
        fake_client = MagicMock()
        fake_client.resolve_city_code.return_value = "GOI"
        fake_client.search_hotels_by_city.return_value = [
            {
                "hotel": {"name": "Test Resort", "cityCode": "GOI"},
                "offers": [{"price": {"total": "15000.00"}, "room": {"typeEstimated": {"category": "STANDARD_ROOM"}}}],
            }
        ]
        monkeypatch.setattr(hotel_agent_module, "_get_amadeus_client", lambda: fake_client)

        state = build_initial_state(make_request())
        result = hotel_agent_module.run_hotel_agent(state)

        assert result["message_log"][0].payload["data_source"] == "amadeus"
        assert result["hotel_result"].name == "Test Resort"
        assert result["hotel_result"].total_price == 15000.0

    def test_falls_back_to_mock_when_no_hotels_found(self, amadeus_configured, monkeypatch):
        fake_client = MagicMock()
        fake_client.resolve_city_code.return_value = "GOI"
        fake_client.search_hotels_by_city.side_effect = AmadeusAPIError("no hotels found")
        monkeypatch.setattr(hotel_agent_module, "_get_amadeus_client", lambda: fake_client)

        state = build_initial_state(make_request())
        result = hotel_agent_module.run_hotel_agent(state)

        assert result["message_log"][0].payload["data_source"] == "mock"
        assert result["hotel_result"] is not None


class TestHotelAgentOwnServiceTier:
    def test_uses_own_service_when_configured_and_successful(self, monkeypatch):
        monkeypatch.setattr(settings, "own_hotel_service_url", "http://localhost:8100")
        fake_client = MagicMock()
        fake_client.search_hotels.return_value = [
            {
                "name": "Atliq Grands", "area": "City Center",
                "price_per_night": 9256.82, "total_price": 46284.1,
                "rating": 4.3, "amenities": ["wifi", "breakfast", "gym"],
            }
        ]
        monkeypatch.setattr(hotel_agent_module, "_get_own_data_client", lambda: fake_client)

        state = build_initial_state(make_request())
        result = hotel_agent_module.run_hotel_agent(state)

        assert result["message_log"][0].payload["data_source"] == "own_service"
        assert result["hotel_result"].name == "Atliq Grands"
        assert result["hotel_result"].rating == 4.3

    def test_own_service_takes_priority_over_amadeus(self, amadeus_configured, monkeypatch):
        monkeypatch.setattr(settings, "own_hotel_service_url", "http://localhost:8100")
        own_client = MagicMock()
        own_client.search_hotels.return_value = [
            {"name": "Real Hotel", "area": "City Center", "price_per_night": 5000.0,
             "total_price": 25000.0, "rating": 4.0, "amenities": ["wifi"]}
        ]
        amadeus_client = MagicMock()
        monkeypatch.setattr(hotel_agent_module, "_get_own_data_client", lambda: own_client)
        monkeypatch.setattr(hotel_agent_module, "_get_amadeus_client", lambda: amadeus_client)

        state = build_initial_state(make_request())
        result = hotel_agent_module.run_hotel_agent(state)

        assert result["message_log"][0].payload["data_source"] == "own_service"
        amadeus_client.resolve_city_code.assert_not_called()

    def test_falls_through_to_amadeus_when_own_service_has_no_coverage(self, amadeus_configured, monkeypatch):
        monkeypatch.setattr(settings, "own_hotel_service_url", "http://localhost:8100")
        own_client = MagicMock()
        own_client.search_hotels.side_effect = hotel_agent_module.OwnHotelDataServiceError("no coverage")
        amadeus_client = MagicMock()
        amadeus_client.resolve_city_code.return_value = "GOI"
        amadeus_client.search_hotels_by_city.return_value = [
            {"hotel": {"name": "Fallback Resort", "cityCode": "GOI"},
             "offers": [{"price": {"total": "12000.00"}, "room": {"typeEstimated": {"category": "STD"}}}]}
        ]
        monkeypatch.setattr(hotel_agent_module, "_get_own_data_client", lambda: own_client)
        monkeypatch.setattr(hotel_agent_module, "_get_amadeus_client", lambda: amadeus_client)

        state = build_initial_state(make_request())
        result = hotel_agent_module.run_hotel_agent(state)

        assert result["message_log"][0].payload["data_source"] == "amadeus"


class TestActivityAgentFallback:
    def test_uses_mock_when_not_configured(self):
        state = build_initial_state(make_request())
        result = activity_agent_module.run_activity_agent(state)
        assert result["message_log"][0].payload["data_source"] == "mock"

    def test_uses_live_data_when_configured_and_successful(self, google_places_configured, monkeypatch):
        fake_client = MagicMock()
        fake_client.text_search.return_value = [
            {"name": "Baga Beach", "price_level": 1},
            {"name": "Anjuna Flea Market", "price_level": 0},
        ]
        monkeypatch.setattr(activity_agent_module, "_get_places_client", lambda: fake_client)

        state = build_initial_state(make_request())
        result = activity_agent_module.run_activity_agent(state)

        assert result["message_log"][0].payload["data_source"] == "google_places"
        names = {a.name for a in result["activity_results"]}
        assert "Baga Beach" in names

    def test_falls_back_to_mock_when_places_api_errors(self, google_places_configured, monkeypatch):
        fake_client = MagicMock()
        fake_client.text_search.side_effect = GooglePlacesAPIError("quota exceeded")
        monkeypatch.setattr(activity_agent_module, "_get_places_client", lambda: fake_client)

        state = build_initial_state(make_request())
        result = activity_agent_module.run_activity_agent(state)

        assert result["message_log"][0].payload["data_source"] == "mock"
        assert len(result["activity_results"]) >= 1


class TestActivityAgentOwnServiceTier:
    def test_uses_own_service_when_interests_match_coverage(self, monkeypatch):
        monkeypatch.setattr(settings, "own_activity_service_url", "http://localhost:8100")
        fake_client = MagicMock()
        fake_client.search_activities.return_value = [
            {"name": "Red Fort", "category": "history", "estimated_cost": 35.0, "duration_hours": 2.5},
        ]
        monkeypatch.setattr(activity_agent_module, "_get_own_data_client", lambda: fake_client)

        state = build_initial_state(make_request(interests=["history"]))
        result = activity_agent_module.run_activity_agent(state)

        assert result["message_log"][0].payload["data_source"] == "own_service"
        assert result["activity_results"][0].name == "Red Fort"
        assert result["activity_results"][0].estimated_cost == 35.0

    def test_falls_through_when_own_service_has_no_matching_interest(self, monkeypatch):
        """
        Own service has real data for this city, but none of it matches
        the user's stated interests (e.g. user wants nightlife, service
        only covers history/nature) — should be treated as a miss and
        fall through, not return an irrelevant activity just because
        the service technically responded.
        """
        monkeypatch.setattr(settings, "own_activity_service_url", "http://localhost:8100")
        fake_client = MagicMock()
        fake_client.search_activities.return_value = [
            {"name": "Red Fort", "category": "history", "estimated_cost": 35.0, "duration_hours": 2.5},
        ]
        monkeypatch.setattr(activity_agent_module, "_get_own_data_client", lambda: fake_client)

        state = build_initial_state(make_request(interests=["nightlife"]))
        result = activity_agent_module.run_activity_agent(state)

        assert result["message_log"][0].payload["data_source"] == "mock"

    def test_own_service_takes_priority_over_google_places(self, google_places_configured, monkeypatch):
        monkeypatch.setattr(settings, "own_activity_service_url", "http://localhost:8100")
        own_client = MagicMock()
        own_client.search_activities.return_value = [
            {"name": "Golconda Fort", "category": "history", "estimated_cost": 25.0, "duration_hours": 2.5},
        ]
        places_client = MagicMock()
        monkeypatch.setattr(activity_agent_module, "_get_own_data_client", lambda: own_client)
        monkeypatch.setattr(activity_agent_module, "_get_places_client", lambda: places_client)

        state = build_initial_state(make_request(interests=["history"]))
        result = activity_agent_module.run_activity_agent(state)

        assert result["message_log"][0].payload["data_source"] == "own_service"
        places_client.text_search.assert_not_called()

    def test_falls_through_to_google_places_when_own_service_has_no_city_coverage(
        self, google_places_configured, monkeypatch
    ):
        monkeypatch.setattr(settings, "own_activity_service_url", "http://localhost:8100")
        own_client = MagicMock()
        own_client.search_activities.side_effect = activity_agent_module.OwnActivityDataServiceError("no coverage")
        places_client = MagicMock()
        places_client.text_search.return_value = [{"name": "Some Place", "price_level": 2}]
        monkeypatch.setattr(activity_agent_module, "_get_own_data_client", lambda: own_client)
        monkeypatch.setattr(activity_agent_module, "_get_places_client", lambda: places_client)

        state = build_initial_state(make_request(interests=["food"]))
        result = activity_agent_module.run_activity_agent(state)

        assert result["message_log"][0].payload["data_source"] == "google_places"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
