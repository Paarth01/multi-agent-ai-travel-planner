import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from datetime import date

import httpx
import pytest
import respx

from clients.amadeus_client import AmadeusClient, AmadeusAPIError
from cache.memory_cache import InMemoryCache

BASE_URL = "https://test.api.amadeus.com"


@pytest.fixture
def client():
    # Fresh, isolated cache per test — without this, tests sharing the
    # same params (e.g. repeated "Goa" lookups) would silently serve a
    # previous test's cached response instead of hitting the mock set
    # up for this test.
    return AmadeusClient(client_id="fake-id", client_secret="fake-secret", base_url=BASE_URL, cache=InMemoryCache())


def mock_token_route():
    return respx.post(f"{BASE_URL}/v1/security/oauth2/token").mock(
        return_value=httpx.Response(200, json={"access_token": "fake-token-123", "expires_in": 1799})
    )


class TestAuth:
    @respx.mock
    def test_fetches_and_caches_token(self, client):
        token_route = mock_token_route()
        code_route = respx.get(f"{BASE_URL}/v1/reference-data/locations").mock(
            return_value=httpx.Response(200, json={"data": [{"iataCode": "GOI"}]})
        )

        # Two DIFFERENT keywords, so the second call can't be served by
        # the (now also cached) city-code lookup — this test isolates
        # token reuse specifically, not city-code caching.
        client.resolve_city_code("Goa")
        client.resolve_city_code("Mumbai")

        assert token_route.call_count == 1
        assert code_route.call_count == 2

    @respx.mock
    def test_auth_failure_raises_amadeus_error(self, client):
        respx.post(f"{BASE_URL}/v1/security/oauth2/token").mock(return_value=httpx.Response(401, json={}))

        with pytest.raises(AmadeusAPIError, match="auth failed"):
            client.resolve_city_code("Goa")

    @respx.mock
    def test_auth_response_missing_field_raises_amadeus_error(self, client):
        respx.post(f"{BASE_URL}/v1/security/oauth2/token").mock(
            return_value=httpx.Response(200, json={"token_type": "Bearer"})  # missing access_token
        )

        with pytest.raises(AmadeusAPIError, match="missing expected field"):
            client.resolve_city_code("Goa")


class TestResolveCityCode:
    @respx.mock
    def test_returns_iata_code_on_match(self, client):
        mock_token_route()
        respx.get(f"{BASE_URL}/v1/reference-data/locations").mock(
            return_value=httpx.Response(200, json={"data": [{"iataCode": "DEL"}]})
        )

        assert client.resolve_city_code("Delhi") == "DEL"

    @respx.mock
    def test_raises_when_no_match_found(self, client):
        mock_token_route()
        respx.get(f"{BASE_URL}/v1/reference-data/locations").mock(return_value=httpx.Response(200, json={"data": []}))

        with pytest.raises(AmadeusAPIError, match="No IATA code found"):
            client.resolve_city_code("Nowhereville")


class TestSearchFlights:
    @respx.mock
    def test_returns_raw_offer_list(self, client):
        mock_token_route()
        respx.get(f"{BASE_URL}/v2/shopping/flight-offers").mock(
            return_value=httpx.Response(200, json={"data": [{"id": "1", "price": {"total": "5000.00"}}]})
        )

        results = client.search_flights("DEL", "GOI", date(2026, 12, 20))
        assert len(results) == 1
        assert results[0]["price"]["total"] == "5000.00"

    @respx.mock
    def test_http_error_raises_amadeus_error(self, client):
        mock_token_route()
        respx.get(f"{BASE_URL}/v2/shopping/flight-offers").mock(return_value=httpx.Response(500))

        with pytest.raises(AmadeusAPIError, match="request to"):
            client.search_flights("DEL", "GOI", date(2026, 12, 20))


class TestSearchHotels:
    @respx.mock
    def test_two_step_flow_returns_offers(self, client):
        mock_token_route()
        respx.get(f"{BASE_URL}/v1/reference-data/locations/hotels/by-city").mock(
            return_value=httpx.Response(200, json={"data": [{"hotelId": "HOTEL1"}, {"hotelId": "HOTEL2"}]})
        )
        respx.get(f"{BASE_URL}/v3/shopping/hotel-offers").mock(
            return_value=httpx.Response(200, json={"data": [{"hotel": {"hotelId": "HOTEL1"}, "offers": []}]})
        )

        results = client.search_hotels_by_city("GOI", date(2026, 12, 20), date(2026, 12, 25))
        assert len(results) == 1

    @respx.mock
    def test_raises_when_no_hotels_in_city(self, client):
        mock_token_route()
        respx.get(f"{BASE_URL}/v1/reference-data/locations/hotels/by-city").mock(
            return_value=httpx.Response(200, json={"data": []})
        )

        with pytest.raises(AmadeusAPIError, match="No hotels found"):
            client.search_hotels_by_city("XXX", date(2026, 12, 20), date(2026, 12, 25))


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
