import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import httpx
import pytest
import respx

from clients.google_places_client import GooglePlacesClient, GooglePlacesAPIError
from cache.memory_cache import InMemoryCache

BASE_URL = "https://maps.googleapis.com/maps/api/place"


@pytest.fixture
def client():
    return GooglePlacesClient(api_key="fake-key", cache=InMemoryCache())


class TestTextSearch:
    @respx.mock
    def test_returns_results_on_ok_status(self, client):
        respx.get(f"{BASE_URL}/textsearch/json").mock(
            return_value=httpx.Response(200, json={"status": "OK", "results": [{"name": "Baga Beach"}]})
        )

        results = client.text_search("beaches in Goa")
        assert len(results) == 1
        assert results[0]["name"] == "Baga Beach"

    @respx.mock
    def test_returns_empty_list_on_zero_results(self, client):
        respx.get(f"{BASE_URL}/textsearch/json").mock(
            return_value=httpx.Response(200, json={"status": "ZERO_RESULTS", "results": []})
        )

        assert client.text_search("nonexistent place xyz") == []

    @respx.mock
    def test_raises_on_error_status(self, client):
        respx.get(f"{BASE_URL}/textsearch/json").mock(
            return_value=httpx.Response(
                200, json={"status": "REQUEST_DENIED", "error_message": "API key invalid"}
            )
        )

        with pytest.raises(GooglePlacesAPIError, match="REQUEST_DENIED"):
            client.text_search("beaches in Goa")

    @respx.mock
    def test_respects_max_results(self, client):
        many_results = [{"name": f"Place {i}"} for i in range(10)]
        respx.get(f"{BASE_URL}/textsearch/json").mock(
            return_value=httpx.Response(200, json={"status": "OK", "results": many_results})
        )

        results = client.text_search("food in Goa", max_results=3)
        assert len(results) == 3

    @respx.mock
    def test_http_error_raises_places_error(self, client):
        respx.get(f"{BASE_URL}/textsearch/json").mock(return_value=httpx.Response(500))

        with pytest.raises(GooglePlacesAPIError, match="request failed"):
            client.text_search("beaches in Goa")


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
