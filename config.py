"""
Centralized configuration for external API credentials.

All fields are optional. When credentials are missing, agents fall back
to the existing mocked data generators automatically — so the app runs
out of the box with zero setup, and real API calls activate the moment
you drop credentials into `.env`.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Own flight data service (data_service/app.py) — real aggregated
    # Indian domestic fare data, self-hosted, no credentials needed.
    # This is tried FIRST for flights when its URL is set, since it has
    # no rate limits and no external dependency. Falls through to
    # Amadeus, then mock, on any failure (including routes it doesn't
    # cover — it's Indian-metro-only, see data_service/seed_data/).
    own_flight_service_url: str | None = None

    # Same service, hotel endpoint — real per-night pricing, names, and
    # ratings from the AtliQ Grands booking dataset. Same priority
    # ordering as flights: own service -> Amadeus -> mock.
    own_hotel_service_url: str | None = None

    # Same service, activity endpoint — real, hand-curated entry fees
    # for fee-gated monuments/museums (4 cities, narrower coverage than
    # flights/hotels — see data_service/seed_data/activity_fees.json).
    own_activity_service_url: str | None = None

    # Amadeus (test environment: https://developers.amadeus.com/self-service)
    amadeus_client_id: str | None = None
    amadeus_client_secret: str | None = None
    amadeus_base_url: str = "https://test.api.amadeus.com"

    # Google Places (https://developers.google.com/maps/documentation/places/web-service)
    google_places_api_key: str | None = None

    # HTTP behavior
    http_timeout_seconds: float = 8.0

    # Caching for live API responses (see cache/). Redis if set and
    # reachable; falls back to in-memory automatically otherwise.
    redis_url: str | None = None
    # Price/availability data goes stale faster than reference data
    # (e.g. city-code lookups), so they get different default TTLs.
    price_cache_ttl_seconds: int = 900       # 15 min
    reference_cache_ttl_seconds: int = 86400  # 24 hours

    # Comma-separated list of allowed frontend origins, e.g.
    # "https://tripsync.vercel.app,http://localhost:5173". "*" (default)
    # is fine for local dev; set explicitly before deploying.
    cors_allowed_origins: str = "*"

    # Persistence — SQLite for saved itineraries, zero-setup default.
    sqlite_db_path: str = "tripsync.db"

    @property
    def cors_allowed_origins_list(self) -> list[str]:
        if self.cors_allowed_origins.strip() == "*":
            return ["*"]
        return [origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()]

    @property
    def cors_is_wildcard(self) -> bool:
        return self.cors_allowed_origins.strip() == "*"

    @property
    def own_flight_service_configured(self) -> bool:
        return bool(self.own_flight_service_url)

    @property
    def own_hotel_service_configured(self) -> bool:
        return bool(self.own_hotel_service_url)

    @property
    def own_activity_service_configured(self) -> bool:
        return bool(self.own_activity_service_url)

    @property
    def amadeus_configured(self) -> bool:
        return bool(self.amadeus_client_id and self.amadeus_client_secret)

    @property
    def google_places_configured(self) -> bool:
        return bool(self.google_places_api_key)


settings = Settings()
