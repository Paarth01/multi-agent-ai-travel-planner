"""
Thin client around the Google Places API (Text Search) for activity
suggestions. Simpler than Amadeus — API key auth, no OAuth dance, no
code resolution needed since Places accepts free-text queries directly.
Responses cached (see cache/) with the reference TTL since attractions
don't change day to day the way flight/hotel prices do.
"""
import httpx

from cache.base import CacheBackend
from cache.factory import get_cache
from cache.keys import build_key
from config import settings


class GooglePlacesAPIError(Exception):
    """Raised for any Google Places auth/network/response failure."""


class GooglePlacesClient:
    def __init__(self, api_key: str, timeout: float = 8.0, cache: CacheBackend | None = None):
        self.api_key = api_key
        self.timeout = timeout
        self.base_url = "https://maps.googleapis.com/maps/api/place"
        self._cache = cache if cache is not None else get_cache()

    def text_search(self, query: str, max_results: int = 5) -> list[dict]:
        """
        Returns raw Google Places result dicts for the caller to map
        into ActivitySuggestion. `query` is expected to already include
        the destination, e.g. "beaches in Goa" — Places' text search
        works best with location baked into the query string itself
        rather than passed as a separate structured field.
        """
        cache_key = build_key("google_places", query=query, max_results=max_results)
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            response = httpx.get(
                f"{self.base_url}/textsearch/json",
                params={"query": query, "key": self.api_key},
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPError as exc:
            raise GooglePlacesAPIError(f"Google Places request failed: {exc}") from exc
        except ValueError as exc:
            raise GooglePlacesAPIError(f"Google Places response was not valid JSON: {exc}") from exc

        status = payload.get("status")
        if status not in ("OK", "ZERO_RESULTS"):
            raise GooglePlacesAPIError(f"Google Places returned status '{status}': {payload.get('error_message', '')}")

        results = payload.get("results", [])[:max_results]
        self._cache.set(cache_key, results, settings.reference_cache_ttl_seconds)
        return results
