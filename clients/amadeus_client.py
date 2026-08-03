"""
Thin client around the Amadeus Self-Service API (test environment).

Handles the parts that are easy to get wrong:
- OAuth2 client-credentials token caching (tokens expire in ~30 min;
  re-fetching per request would work but wastes a round trip on every
  single search)
- IATA city/airport code resolution — Amadeus's flight/hotel search
  endpoints require codes like "DEL" / "GOI", not free-text city names
  like "Delhi" / "Goa", which is what the trip form actually collects

Raises AmadeusAPIError on any failure (auth, network, unexpected
response shape) so callers (the agent modules) can catch a single
exception type and fall back to mock data.
"""
import time
from datetime import date

import httpx

from cache.base import CacheBackend
from cache.factory import get_cache
from cache.keys import build_key
from config import settings


class AmadeusAPIError(Exception):
    """Raised for any Amadeus auth/network/response failure."""


class AmadeusClient:
    def __init__(self, client_id: str, client_secret: str, base_url: str, timeout: float = 8.0, cache: CacheBackend | None = None):
        self.client_id = client_id
        self.client_secret = client_secret
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._token: str | None = None
        self._token_expires_at: float = 0.0
        self._cache = cache if cache is not None else get_cache()

    def _get_access_token(self) -> str:
        # Reuse the cached token until ~60s before it actually expires,
        # to avoid a race where it expires mid-request.
        if self._token and time.time() < self._token_expires_at - 60:
            return self._token

        try:
            response = httpx.post(
                f"{self.base_url}/v1/security/oauth2/token",
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPError as exc:
            raise AmadeusAPIError(f"Amadeus auth failed: {exc}") from exc
        except ValueError as exc:
            raise AmadeusAPIError(f"Amadeus auth returned non-JSON response: {exc}") from exc

        try:
            self._token = payload["access_token"]
            self._token_expires_at = time.time() + payload["expires_in"]
        except KeyError as exc:
            raise AmadeusAPIError(f"Amadeus auth response missing expected field: {exc}") from exc

        return self._token

    def _authed_get(self, path: str, params: dict) -> dict:
        token = self._get_access_token()
        try:
            response = httpx.get(
                f"{self.base_url}{path}",
                params=params,
                headers={"Authorization": f"Bearer {token}"},
                timeout=self.timeout,
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as exc:
            raise AmadeusAPIError(f"Amadeus request to {path} failed: {exc}") from exc
        except ValueError as exc:
            raise AmadeusAPIError(f"Amadeus response from {path} was not valid JSON: {exc}") from exc

    def resolve_city_code(self, keyword: str) -> str:
        """
        Resolves a free-text city/airport name (e.g. "Goa") to an IATA
        code (e.g. "GOI") via the Airport & City Search endpoint. Raises
        AmadeusAPIError if no match is found, so callers can fall back
        to mock data rather than searching flights against a garbage code.

        Cached with a long TTL (reference_cache_ttl_seconds, default
        24h) since city/airport codes essentially never change day to
        day — no reason to re-resolve "Goa" -> "GOI" on every search.
        """
        cache_key = build_key("amadeus_city_code", keyword=keyword)
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        data = self._authed_get(
            "/v1/reference-data/locations",
            {"keyword": keyword, "subType": "CITY,AIRPORT", "page[limit]": 1},
        )
        results = data.get("data", [])
        if not results:
            raise AmadeusAPIError(f"No IATA code found for '{keyword}'")
        code = results[0]["iataCode"]
        self._cache.set(cache_key, code, settings.reference_cache_ttl_seconds)
        return code

    def search_flights(
        self, origin_code: str, destination_code: str, departure_date: date, adults: int = 1, max_results: int = 5
    ) -> list[dict]:
        """Returns raw Amadeus flight-offer dicts (unparsed) for the caller to map into FlightOption."""
        cache_key = build_key(
            "amadeus_flights", origin_code=origin_code, destination_code=destination_code,
            departure_date=departure_date.isoformat(), adults=adults, max_results=max_results,
        )
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        data = self._authed_get(
            "/v2/shopping/flight-offers",
            {
                "originLocationCode": origin_code,
                "destinationLocationCode": destination_code,
                "departureDate": departure_date.isoformat(),
                "adults": adults,
                "max": max_results,
                "currencyCode": "INR",
            },
        )
        results = data.get("data", [])
        self._cache.set(cache_key, results, settings.price_cache_ttl_seconds)
        return results

    def search_hotels_by_city(self, city_code: str, check_in: date, check_out: date, adults: int = 1) -> list[dict]:
        """
        Two-step Amadeus flow: first list hotel IDs in the city, then
        fetch live offers for those IDs. Returns raw hotel-offer dicts.
        """
        cache_key = build_key(
            "amadeus_hotels", city_code=city_code,
            check_in=check_in.isoformat(), check_out=check_out.isoformat(), adults=adults,
        )
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        hotel_list = self._authed_get(
            "/v1/reference-data/locations/hotels/by-city",
            {"cityCode": city_code},
        )
        hotel_ids = [h["hotelId"] for h in hotel_list.get("data", [])[:20]]  # cap fan-out to 20 hotels
        if not hotel_ids:
            raise AmadeusAPIError(f"No hotels found for city code '{city_code}'")

        offers = self._authed_get(
            "/v3/shopping/hotel-offers",
            {
                "hotelIds": ",".join(hotel_ids),
                "checkInDate": check_in.isoformat(),
                "checkOutDate": check_out.isoformat(),
                "adults": adults,
                "currency": "INR",
            },
        )
        results = offers.get("data", [])
        self._cache.set(cache_key, results, settings.price_cache_ttl_seconds)
        return results
