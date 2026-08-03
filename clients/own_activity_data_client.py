"""
Client for the own activity data endpoint (data_service/app.py), which
serves real, hand-curated entry fees for fee-gated monuments/museums in
4 Indian metro cities. Narrower coverage than the flight/hotel own
services (see data_service/seed_data/activity_fees.json's source note)
— many city/category combos genuinely have no data here and correctly
404, which the activity agent treats as "fall through to the next tier."
"""
import httpx

from cache.base import CacheBackend
from cache.factory import get_cache
from cache.keys import build_key
from config import settings


class OwnActivityDataServiceError(Exception):
    """Raised for any failure talking to the own activity data service."""


class OwnActivityDataClient:
    def __init__(self, base_url: str, timeout: float = 8.0, cache: CacheBackend | None = None):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._cache = cache if cache is not None else get_cache()

    def search_activities(self, city: str, category: str | None = None, limit: int = 5) -> list[dict]:
        cache_key = build_key("own_activity", city=city, category=category, limit=limit)
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            params = {"city": city, "limit": limit}
            if category:
                params["category"] = category
            response = httpx.get(f"{self.base_url}/activities/search", params=params, timeout=self.timeout)
            if response.status_code == 404:
                # Expected — real coverage is narrow (fee-gated monuments
                # only, 4 cities) — not a service failure, just no data.
                raise OwnActivityDataServiceError(f"No data for city '{city}': {response.json().get('detail')}")
            response.raise_for_status()
            results = response.json()
        except httpx.HTTPError as exc:
            raise OwnActivityDataServiceError(f"Own activity data service request failed: {exc}") from exc
        except ValueError as exc:
            raise OwnActivityDataServiceError(f"Own activity data service returned non-JSON response: {exc}") from exc

        # Real fee data — use a longer TTL than prices (reference-like,
        # published fees don't fluctuate the way flight/hotel prices do).
        self._cache.set(cache_key, results, settings.reference_cache_ttl_seconds)
        return results
