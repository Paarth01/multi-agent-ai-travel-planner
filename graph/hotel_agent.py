"""
Hotel Agent — searches for hotels within the current budget ceiling.

Three-tier data source, tried in order:
1. Own hotel data service (data_service/app.py) — real per-night
   pricing, real hotel names, real ratings from the AtliQ Grands
   booking dataset, self-hosted, no rate limits. Only covers the 4
   Indian metros in its seed dataset.
2. Amadeus — broader coverage (including international), but requires
   credentials and is rate-limited on the free test tier.
3. Mocked data generator — always available, zero setup.

Falls through to the next tier on any failure, same rationale as
flight_agent.py.
"""
import random
from datetime import date

from clients.amadeus_client import AmadeusClient, AmadeusAPIError
from clients.own_hotel_data_client import OwnHotelDataClient, OwnHotelDataServiceError
from config import settings
from schemas.messages import AgentMessage, AgentID, TaskStatus, HotelOption
from graph.state import TravelPlannerState


HOTEL_NAME_POOL = [
    "Beach Resort", "Boutique Stay", "Grand Palace Hotel",
    "Harbor View Inn", "The Local Homestay", "Skyline Suites",
]
AREA_POOL = ["Old Town", "Beachfront", "City Center", "Near Airport", "Hillside"]

# Same reasoning as MIN_FLIGHT_PRICE in flight_agent.py — a real room
# never actually costs ₹20/night just because the ceiling shrank.
MIN_PRICE_PER_NIGHT = 800.0

_amadeus_client: AmadeusClient | None = None
_own_data_client: OwnHotelDataClient | None = None


def _get_amadeus_client() -> AmadeusClient:
    global _amadeus_client
    if _amadeus_client is None:
        _amadeus_client = AmadeusClient(
            client_id=settings.amadeus_client_id,
            client_secret=settings.amadeus_client_secret,
            base_url=settings.amadeus_base_url,
            timeout=settings.http_timeout_seconds,
        )
    return _amadeus_client


def _get_own_data_client() -> OwnHotelDataClient:
    global _own_data_client
    if _own_data_client is None:
        _own_data_client = OwnHotelDataClient(
            base_url=settings.own_hotel_service_url,
            timeout=settings.http_timeout_seconds,
        )
    return _own_data_client


def _map_amadeus_hotel_offer(offer: dict, nights: int) -> HotelOption:
    hotel = offer["hotel"]
    # Amadeus v3 hotel-offers can return multiple room offers per
    # hotel; take the cheapest one.
    cheapest_offer = min(offer["offers"], key=lambda o: float(o["price"]["total"]))
    total_price = float(cheapest_offer["price"]["total"])

    return HotelOption(
        name=hotel.get("name", "Unknown Hotel"),
        # Amadeus's hotel-offers endpoint doesn't return neighborhood/area
        # data — that lives in a separate Hotel Content API call we're not
        # making here to keep this to one round trip. Falls back to city name.
        area=hotel.get("cityCode", "City Center"),
        price_per_night=round(total_price / max(nights, 1), 2),
        total_price=round(total_price, 2),
        # Amadeus doesn't return a star/user rating on this endpoint either.
        rating=None,
        amenities=[a.lower() for a in cheapest_offer.get("room", {}).get("typeEstimated", {}).get("category", "").split("_") if a],
    )


def _map_own_service_result(result: dict) -> HotelOption:
    return HotelOption(
        name=result["name"],
        area=result["area"],
        price_per_night=float(result["price_per_night"]),
        total_price=float(result["total_price"]),
        rating=result.get("rating"),
        amenities=result.get("amenities", []),
    )


def _live_search_hotels_own_service(destination: str, nights: int) -> list[HotelOption]:
    client = _get_own_data_client()
    raw_results = client.search_hotels(destination, nights)
    return [_map_own_service_result(r) for r in raw_results]


def _live_search_hotels_amadeus(destination: str, check_in: date, check_out: date, nights: int) -> list[HotelOption]:
    client = _get_amadeus_client()
    city_code = client.resolve_city_code(destination)
    raw_offers = client.search_hotels_by_city(city_code, check_in, check_out)
    return [_map_amadeus_hotel_offer(o, nights) for o in raw_offers]


def _mock_search_hotels(destination: str, nights: int, budget_ceiling: float) -> list[HotelOption]:
    per_night_ceiling = budget_ceiling / max(nights, 1)
    options = []
    price_ratios = [0.70, 0.88, 1.10]

    for ratio in price_ratios:
        price_per_night = round(max(per_night_ceiling * ratio, MIN_PRICE_PER_NIGHT), 2)
        options.append(HotelOption(
            name=random.choice(HOTEL_NAME_POOL),
            area=random.choice(AREA_POOL),
            price_per_night=price_per_night,
            total_price=round(price_per_night * nights, 2),
            rating=round(random.uniform(3.5, 4.8), 1),
            amenities=random.sample(
                ["wifi", "pool", "breakfast", "gym", "parking", "spa"], k=3
            ),
        ))
    return options


def run_hotel_agent(state: TravelPlannerState) -> dict:
    request = state["request"]
    ceiling = state["budget_ceilings"]["hotel"]
    nights = max((request.end_date - request.start_date).days, 1)
    data_source = "mock"
    options = None

    try:
        # Tier 1: own data service (real stats, no rate limits, Indian metros only)
        if settings.own_hotel_service_configured:
            try:
                options = _live_search_hotels_own_service(request.destination, nights)
                if not options:
                    raise OwnHotelDataServiceError("Own service returned zero results")
                data_source = "own_service"
            except OwnHotelDataServiceError:
                options = None

        # Tier 2: Amadeus (broader coverage, needs credentials)
        if options is None and settings.amadeus_configured:
            try:
                options = _live_search_hotels_amadeus(request.destination, request.start_date, request.end_date, nights)
                if not options:
                    raise AmadeusAPIError("Amadeus returned zero hotel offers")
                data_source = "amadeus"
            except AmadeusAPIError:
                options = None

        # Tier 3: mock (always available)
        if options is None:
            options = _mock_search_hotels(request.destination, nights, ceiling)
            data_source = "mock"

        within_budget = [o for o in options if o.total_price <= ceiling]
        chosen = min(within_budget, key=lambda o: o.total_price) if within_budget else min(options, key=lambda o: o.total_price)

        message = AgentMessage(
            agent_id=AgentID.HOTEL,
            task_type="search_hotels",
            status=TaskStatus.COMPLETED,
            payload={
                "chosen": chosen.model_dump(),
                "candidates_considered": len(options),
                "nights": nights,
                "data_source": data_source,
            },
            confidence=1.0 if within_budget else 0.6,
            budget_used=chosen.total_price,
        )

        return {
            "hotel_result": chosen,
            "message_log": [message],
        }

    except Exception as exc:  # pragma: no cover
        message = AgentMessage(
            agent_id=AgentID.HOTEL,
            task_type="search_hotels",
            status=TaskStatus.FAILED,
            payload={"data_source": data_source},
            error=str(exc),
        )
        return {
            "hotel_result": None,
            "message_log": [message],
        }
