"""
Client for the self-hosted flight data microservice (data_service/app.py),
which serves realistic prices sampled from real aggregated Indian
domestic flight data. This is the primary real-data source for flights
— no third-party credentials, no rate limits, fully under our control.
Amadeus remains available as an alternate/international-route option;
see config.py for priority order.

Responses are cached (see cache/) so repeated identical searches —
which happen naturally during the negotiation loop, since a
reallocation round re-queries the same route/date, just against a new
budget ceiling that's applied client-side after the fact — don't repeat
the network round trip.
"""
from datetime import date

import httpx

from cache.base import CacheBackend
from cache.factory import get_cache
from cache.keys import build_key
from config import settings


class OwnDataServiceError(Exception):
    """Raised for any failure talking to the own flight data service."""


class OwnFlightDataClient:
    def __init__(self, base_url: str, timeout: float = 8.0, cache: CacheBackend | None = None):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._cache = cache if cache is not None else get_cache()

    def search_flights(
        self, origin: str, destination: str, departure_date: date, travel_class: str = "Economy", limit: int = 5
    ) -> list[dict]:
        cache_key = build_key(
            "own_flight", origin=origin, destination=destination,
            departure_date=departure_date.isoformat(), travel_class=travel_class, limit=limit,
        )
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            response = httpx.get(
                f"{self.base_url}/flights/search",
                params={
                    "origin": origin,
                    "destination": destination,
                    "departure_date": departure_date.isoformat(),
                    "travel_class": travel_class,
                    "limit": limit,
                },
                timeout=self.timeout,
            )
            if response.status_code == 404:
                # Expected for routes outside the seed dataset's coverage
                # (only 6 Indian metros) — not a service failure, just no data.
                raise OwnDataServiceError(f"No data for route {origin} -> {destination}: {response.json().get('detail')}")
            response.raise_for_status()
            results = response.json()
        except httpx.HTTPError as exc:
            raise OwnDataServiceError(f"Own flight data service request failed: {exc}") from exc
        except ValueError as exc:
            raise OwnDataServiceError(f"Own flight data service returned non-JSON response: {exc}") from exc

        self._cache.set(cache_key, results, settings.price_cache_ttl_seconds)
        return results
