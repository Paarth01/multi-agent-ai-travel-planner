import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from datetime import date

import httpx
import pytest
import respx

from cache.memory_cache import InMemoryCache
from clients.own_flight_data_client import OwnFlightDataClient
from clients.own_hotel_data_client import OwnHotelDataClient

BASE_URL = "http://localhost:8100"


class TestOwnFlightDataClientCaching:
    @respx.mock
    def test_second_identical_call_skips_network(self):
        client = OwnFlightDataClient(base_url=BASE_URL, cache=InMemoryCache())
        route = respx.get(f"{BASE_URL}/flights/search").mock(
            return_value=httpx.Response(200, json=[{"airline": "IndiGo", "flight_number": "6E1", "price": 5000.0,
                                                       "departure_time": "2026-12-20T06:00:00",
                                                       "arrival_time": "2026-12-20T08:00:00", "stops": 0}])
        )

        client.search_flights("Delhi", "Mumbai", date(2026, 12, 20))
        client.search_flights("Delhi", "Mumbai", date(2026, 12, 20))

        assert route.call_count == 1  # second call served from cache

    @respx.mock
    def test_different_params_are_not_cache_hits(self):
        client = OwnFlightDataClient(base_url=BASE_URL, cache=InMemoryCache())
        route = respx.get(f"{BASE_URL}/flights/search").mock(
            return_value=httpx.Response(200, json=[])
        )

        client.search_flights("Delhi", "Mumbai", date(2026, 12, 20))
        client.search_flights("Delhi", "Bangalore", date(2026, 12, 20))  # different destination

        assert route.call_count == 2  # different params, no cache hit


class TestOwnHotelDataClientCaching:
    @respx.mock
    def test_second_identical_call_skips_network(self):
        client = OwnHotelDataClient(base_url=BASE_URL, cache=InMemoryCache())
        route = respx.get(f"{BASE_URL}/hotels/search").mock(
            return_value=httpx.Response(200, json=[{"name": "Atliq Grands", "area": "City Center",
                                                       "price_per_night": 9000.0, "total_price": 27000.0,
                                                       "rating": 4.0, "amenities": ["wifi"]}])
        )

        client.search_hotels("Mumbai", nights=3)
        client.search_hotels("Mumbai", nights=3)

        assert route.call_count == 1


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
