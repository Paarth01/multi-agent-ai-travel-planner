"""
Flight Agent — searches for flights within the current budget ceiling.

Three-tier data source, tried in order:
1. Own flight data service (data_service/app.py) — real aggregated
   Indian domestic fare statistics, self-hosted, no rate limits.
   Only covers routes between the 6 major metros in its seed dataset.
2. Amadeus — broader route coverage (including international), but
   requires credentials and is rate-limited on the free test tier.
3. Mocked data generator — always available, zero setup.

Falls through to the next tier on any failure (missing config, no
coverage for the route, network error), so the app never fails a trip
plan just because one upstream provider had a bad day.
"""
import logging
import random
from datetime import date, datetime, timedelta

from clients.amadeus_client import AmadeusClient, AmadeusAPIError
from clients.own_flight_data_client import OwnFlightDataClient, OwnDataServiceError
from config import settings
from schemas.messages import AgentMessage, AgentID, TaskStatus, FlightOption
from graph.state import TravelPlannerState

logger = logging.getLogger(__name__)


AIRLINES = ["IndiGo", "Air India", "SpiceJet", "Vistara", "Akasa Air"]
# Amadeus flight offers return IATA carrier codes, not display names —
# best-effort lookup for the common ones; falls back to the raw code.
CARRIER_NAMES = {"6E": "IndiGo", "AI": "Air India", "SG": "SpiceJet", "UK": "Vistara", "QP": "Akasa Air"}

# Real flights have a floor cost regardless of budget — a domestic flight
# never actually costs ₹100 just because the ceiling shrank. Without this,
# the ceiling-proportional pricing below made it impossible for a small
# budget to ever exceed its own ceiling, which meant the negotiation loop
# could never trigger from budget size alone.
MIN_FLIGHT_PRICE = 2500.0

_amadeus_client: AmadeusClient | None = None
_own_data_client: OwnFlightDataClient | None = None


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


def _get_own_data_client() -> OwnFlightDataClient:
    global _own_data_client
    if _own_data_client is None:
        _own_data_client = OwnFlightDataClient(
            base_url=settings.own_flight_service_url,
            timeout=settings.http_timeout_seconds,
        )
    return _own_data_client


def _map_amadeus_offer(offer: dict) -> FlightOption:
    segments = offer["itineraries"][0]["segments"]
    first_segment, last_segment = segments[0], segments[-1]
    carrier_code = first_segment["carrierCode"]

    return FlightOption(
        airline=CARRIER_NAMES.get(carrier_code, carrier_code),
        flight_number=f"{carrier_code}{first_segment['number']}",
        departure_time=datetime.fromisoformat(first_segment["departure"]["at"]),
        arrival_time=datetime.fromisoformat(last_segment["arrival"]["at"]),
        price=float(offer["price"]["total"]),
        stops=len(segments) - 1,
    )


def _map_own_service_result(result: dict) -> FlightOption:
    return FlightOption(
        airline=result["airline"],
        flight_number=result["flight_number"],
        departure_time=datetime.fromisoformat(result["departure_time"]),
        arrival_time=datetime.fromisoformat(result["arrival_time"]),
        price=float(result["price"]),
        stops=result["stops"],
    )


def _live_search_flights_own_service(origin: str, destination: str, departure_date: date) -> list[FlightOption]:
    client = _get_own_data_client()
    raw_results = client.search_flights(origin, destination, departure_date)
    return [_map_own_service_result(r) for r in raw_results]


def _live_search_flights_amadeus(origin: str, destination: str, departure_date: date) -> list[FlightOption]:
    client = _get_amadeus_client()
    origin_code = client.resolve_city_code(origin)
    destination_code = client.resolve_city_code(destination)
    raw_offers = client.search_flights(origin_code, destination_code, departure_date)
    return [_map_amadeus_offer(o) for o in raw_offers]


def _mock_search_flights(origin: str, destination: str, start_date, budget_ceiling: float) -> list[FlightOption]:
    """
    Generates a handful of plausible flight options priced around the
    given ceiling — some under, some slightly over, so the pricing
    agent's logic has something realistic to react to. Prices never drop
    below MIN_FLIGHT_PRICE, so a ceiling far below realistic market cost
    correctly produces an over-ceiling result rather than a false fit.
    """
    options = []
    base_departure = datetime.combine(start_date, datetime.min.time()) + timedelta(hours=6)

    # Price options spread relative to ceiling: cheaper/direct, mid, pricier/nonstop
    price_ratios = [0.75, 0.90, 1.05]
    for i, ratio in enumerate(price_ratios):
        price = round(max(budget_ceiling * ratio, MIN_FLIGHT_PRICE), 2)
        stops = 0 if ratio >= 0.95 else random.choice([0, 1])
        options.append(FlightOption(
            airline=random.choice(AIRLINES),
            flight_number=f"{random.choice(['6E', 'AI', 'SG', 'UK', 'QP'])}{random.randint(100, 999)}",
            departure_time=base_departure + timedelta(hours=i * 3),
            arrival_time=base_departure + timedelta(hours=i * 3 + 2, minutes=30),
            price=price,
            stops=stops,
        ))
    return options


def run_flight_agent(state: TravelPlannerState) -> dict:
    request = state["request"]
    ceiling = state["budget_ceilings"]["flight"]
    data_source = "mock"
    options = None

    try:
        # Tier 1: own data service (real stats, no rate limits, Indian metros only)
        if settings.own_flight_service_configured:
            try:
                options = _live_search_flights_own_service(request.origin, request.destination, request.start_date)
                if not options:
                    raise OwnDataServiceError("Own service returned zero results")
                data_source = "own_service"
            except OwnDataServiceError as exc:
                  logger.warning("Own flight data service unavailable, falling back: %s", exc)
                  options = None

        # Tier 2: Amadeus (broader coverage, needs credentials)
        if options is None and settings.amadeus_configured:
            try:
                options = _live_search_flights_amadeus(request.origin, request.destination, request.start_date)
                if not options:
                    raise AmadeusAPIError("Amadeus returned zero flight offers")
                data_source = "amadeus"
            except AmadeusAPIError:
                options = None

        # Tier 3: mock (always available)
        if options is None:
            options = _mock_search_flights(request.origin, request.destination, request.start_date, ceiling)
            data_source = "mock"

        # Pick the cheapest option that fits the ceiling; if none fit,
        # take the cheapest available and let the pricing agent flag it.
        within_budget = [o for o in options if o.price <= ceiling]
        chosen = min(within_budget, key=lambda o: o.price) if within_budget else min(options, key=lambda o: o.price)

        message = AgentMessage(
            agent_id=AgentID.FLIGHT,
            task_type="search_flights",
            status=TaskStatus.COMPLETED,
            payload={
                "chosen": chosen.model_dump(),
                "candidates_considered": len(options),
                "data_source": data_source,
            },
            confidence=1.0 if within_budget else 0.6,  # lower confidence if we had to exceed ceiling
            budget_used=chosen.price,
        )

        return {
            "flight_result": chosen,
            "message_log": [message],
        }

    except Exception as exc:  # pragma: no cover - defensive path for unexpected failures
        message = AgentMessage(
            agent_id=AgentID.FLIGHT,
            task_type="search_flights",
            status=TaskStatus.FAILED,
            payload={"data_source": data_source},
            error=str(exc),
        )
        return {
            "flight_result": chosen,
            "message_log": [message],
            "flight_at_floor": not bool(within_budget),
        }
