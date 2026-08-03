"""
Activity Agent — suggests day-by-day activities within the budget
ceiling, filtered by the user's stated interests.

Three-tier data source, tried in order:
1. Own activity data service (data_service/app.py) — real, hand-curated
   entry fees for fee-gated monuments/museums, 4 Indian metro cities.
   Coverage is narrow (only "history"/"nature" categories exist in the
   curated data — see data_service/seed_data/activity_fees.json's
   source note) and is filtered locally against the user's interests;
   if none of the user's interests match what's covered for this city,
   this tier is treated as a miss and falls through.
2. Google Places — broader coverage, needs credentials, costs are
   estimated from price_level heuristics (not real prices).
3. Mocked data generator — always available, zero setup.
"""
import random

from clients.google_places_client import GooglePlacesClient, GooglePlacesAPIError
from clients.own_activity_data_client import OwnActivityDataClient, OwnActivityDataServiceError
from config import settings
from schemas.messages import AgentMessage, AgentID, TaskStatus, ActivitySuggestion
from graph.state import TravelPlannerState


# category -> pool of (name, base_cost, duration_hours)
ACTIVITY_POOL = {
    "beaches": [
        ("Water sports session", 1500, 3), ("Sunset beach walk", 0, 1.5),
        ("Scuba diving trip", 3500, 4),
    ],
    "nightlife": [
        ("Beach club night", 2000, 4), ("Rooftop bar hop", 1200, 3),
        ("Live music lounge", 800, 2.5),
    ],
    "food": [
        ("Local food crawl", 1000, 3), ("Cooking class", 1800, 2.5),
        ("Fine dining experience", 3000, 2),
    ],
    "history": [
        ("Heritage walking tour", 500, 2.5), ("Museum visit", 300, 2),
        ("Fort/monument tour", 400, 2),
    ],
    "nature": [
        ("Hiking trip", 600, 4), ("Wildlife sanctuary visit", 1200, 3),
        ("Waterfall trek", 900, 3.5),
    ],
}
DEFAULT_POOL = [("City sightseeing tour", 700, 3), ("Local market visit", 200, 1.5)]

_places_client: GooglePlacesClient | None = None
_own_data_client: OwnActivityDataClient | None = None


def _get_places_client() -> GooglePlacesClient:
    global _places_client
    if _places_client is None:
        _places_client = GooglePlacesClient(
            api_key=settings.google_places_api_key,
            timeout=settings.http_timeout_seconds,
        )
    return _places_client


def _get_own_data_client() -> OwnActivityDataClient:
    global _own_data_client
    if _own_data_client is None:
        _own_data_client = OwnActivityDataClient(
            base_url=settings.own_activity_service_url,
            timeout=settings.http_timeout_seconds,
        )
    return _own_data_client


def _estimate_cost_from_price_level(price_level: int | None) -> float:
    """
    Google Places' price_level is a 0-4 scale with no currency attached.
    Mapping to an approximate INR cost so the pricing agent has a number
    to negotiate with. This is a rough heuristic, not real pricing —
    swap for a real pricing/booking API if this needs to be accurate.
    """
    if price_level is None:
        return 500.0
    return {0: 0.0, 1: 300.0, 2: 800.0, 3: 1800.0, 4: 3500.0}.get(price_level, 500.0)


def _live_search_activities_own_service(
    interests: list[str], destination: str, trip_days: int
) -> list[ActivitySuggestion]:
    client = _get_own_data_client()
    # Single call for the whole city (no category filter), then filter
    # locally against the user's interests — cheaper than one call per
    # interest, and lets us see the full real coverage for this city.
    raw_results = client.search_activities(destination)
    matched = [r for r in raw_results if r["category"] in interests] if interests else raw_results

    if not matched:
        raise OwnActivityDataServiceError(
            f"Own service has data for {destination} but none of it matches interests {interests}"
        )

    return [
        ActivitySuggestion(
            name=r["name"],
            category=r["category"],
            day=((i - 1) % max(trip_days, 1)) + 1,
            estimated_cost=float(r["estimated_cost"]),
            duration_hours=r["duration_hours"],
        )
        for i, r in enumerate(matched, start=1)
    ]


def _live_search_activities_google(interests: list[str], destination: str, trip_days: int) -> list[ActivitySuggestion]:
    client = _get_places_client()
    queries = [f"{interest} in {destination}" for interest in interests] or [f"tourist attractions in {destination}"]

    suggestions: list[ActivitySuggestion] = []
    day = 1
    for query, interest in zip(queries, interests or ["general"]):
        results = client.text_search(query, max_results=3)
        for place in results:
            suggestions.append(ActivitySuggestion(
                name=place.get("name", "Unnamed activity"),
                category=interest,
                day=((day - 1) % max(trip_days, 1)) + 1,
                estimated_cost=_estimate_cost_from_price_level(place.get("price_level")),
                duration_hours=2.0,  # Places doesn't return this; reasonable default
            ))
            day += 1

    return suggestions


def _mock_search_activities(interests: list[str], trip_days: int, budget_ceiling: float) -> list[ActivitySuggestion]:
    matched_pools = [ACTIVITY_POOL[i] for i in interests if i in ACTIVITY_POOL]
    if not matched_pools:
        matched_pools = [DEFAULT_POOL]

    candidates: list[ActivitySuggestion] = []
    day = 1
    for pool in matched_pools:
        for name, cost, duration in pool:
            candidates.append(ActivitySuggestion(
                name=name,
                category=next((i for i in interests if i in ACTIVITY_POOL and (name, cost, duration) in ACTIVITY_POOL[i]), "general"),
                day=((day - 1) % max(trip_days, 1)) + 1,
                estimated_cost=float(cost),
                duration_hours=duration,
            ))
            day += 1

    # Greedily fill within the ceiling, cheapest first, capped at 2 per day
    candidates.sort(key=lambda a: a.estimated_cost)
    selected: list[ActivitySuggestion] = []
    running_total = 0.0
    per_day_count: dict[int, int] = {}

    for activity in candidates:
        if per_day_count.get(activity.day, 0) >= 2:
            continue
        if running_total + activity.estimated_cost > budget_ceiling and selected:
            continue  # skip if it would blow the ceiling, unless we have nothing yet
        selected.append(activity)
        running_total += activity.estimated_cost
        per_day_count[activity.day] = per_day_count.get(activity.day, 0) + 1

    return selected or candidates[:1]  # guarantee at least one suggestion


def run_activity_agent(state: TravelPlannerState) -> dict:
    request = state["request"]
    ceiling = state["budget_ceilings"]["activity"]
    trip_days = max((request.end_date - request.start_date).days, 1)
    data_source = "mock"
    activities = None

    try:
        # Tier 1: own data service (real fees, narrow coverage — 4 cities, 2 categories)
        if settings.own_activity_service_configured:
            try:
                activities = _live_search_activities_own_service(request.interests, request.destination, trip_days)
                data_source = "own_service"
            except OwnActivityDataServiceError:
                activities = None

        # Tier 2: Google Places (broader coverage, needs credentials)
        if activities is None and settings.google_places_configured:
            try:
                activities = _live_search_activities_google(request.interests, request.destination, trip_days)
                if not activities:
                    raise GooglePlacesAPIError("Google Places returned zero results")
                data_source = "google_places"
            except GooglePlacesAPIError:
                activities = None

        # Tier 3: mock (always available)
        if activities is None:
            activities = _mock_search_activities(request.interests, trip_days, ceiling)
            data_source = "mock"

        total_cost = sum(a.estimated_cost for a in activities)

        message = AgentMessage(
            agent_id=AgentID.ACTIVITY,
            task_type="search_activities",
            status=TaskStatus.COMPLETED,
            payload={
                "activities": [a.model_dump() for a in activities],
                "count": len(activities),
                "data_source": data_source,
            },
            confidence=1.0 if total_cost <= ceiling else 0.6,
            budget_used=total_cost,
        )

        return {
            "activity_results": activities,
            "message_log": [message],
        }

    except Exception as exc:  # pragma: no cover
        message = AgentMessage(
            agent_id=AgentID.ACTIVITY,
            task_type="search_activities",
            status=TaskStatus.FAILED,
            payload={"data_source": data_source},
            error=str(exc),
        )
        return {
            "activity_results": [],
            "message_log": [message],
        }
