"""
Client for the own hotel data endpoint (data_service/app.py), which
serves realistic per-night hotel prices, real hotel names, and real
ratings sampled from the AtliQ Grands booking dataset. Same rationale
as OwnFlightDataClient — no third-party credentials, no rate limits,
responses cached (see cache/) so repeated searches during the
negotiation loop don't repeat the network round trip.
"""
import httpx

from cache.base import CacheBackend
from cache.factory import get_cache
from cache.keys import build_key
from config import settings


class OwnHotelDataServiceError(Exception):
    """Raised for any failure talking to the own hotel data service."""


class OwnHotelDataClient:
    def __init__(self, base_url: str, timeout: float = 8.0, cache: CacheBackend | None = None):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._cache = cache if cache is not None else get_cache()

    def search_hotels(self, city: str, nights: int, room_class: str | None = None, limit: int = 5) -> list[dict]:
        cache_key = build_key("own_hotel", city=city, nights=nights, room_class=room_class, limit=limit)
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            params = {"city": city, "nights": nights, "limit": limit}
            if room_class:
                params["room_class"] = room_class
            response = httpx.get(f"{self.base_url}/hotels/search", params=params, timeout=self.timeout)
            if response.status_code == 404:
                # Expected for cities outside the seed dataset's coverage
                # (only 4 Indian metros) — not a service failure, just no data.
                raise OwnHotelDataServiceError(f"No data for city '{city}': {response.json().get('detail')}")
            response.raise_for_status()
            results = response.json()
        except httpx.HTTPError as exc:
            raise OwnHotelDataServiceError(f"Own hotel data service request failed: {exc}") from exc
        except ValueError as exc:
            raise OwnHotelDataServiceError(f"Own hotel data service returned non-JSON response: {exc}") from exc

        self._cache.set(cache_key, results, settings.price_cache_ttl_seconds)
        return results
