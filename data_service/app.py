"""
Own travel data microservice — serves realistic flight and hotel search
results sampled from real, aggregated pricing data:

- Flights: Kaggle "Flight Price Prediction" dataset, ~300K rows of 2022
  fares across 6 Indian metro cities. See scripts/build_flight_seed.py.
- Hotels: "AtliQ Grands" hotel booking dataset, ~134K real bookings
  across 4 Indian metro cities, with real per-stay revenue and real
  customer ratings. See scripts/build_hotel_seed.py.

Rather than replaying fixed historical rows, each request samples a
fresh value from the real per-segment distribution (normal distribution
parameterized by that segment's actual mean/std, clipped to its actual
observed min/max) — so repeated searches vary realistically instead of
returning identical numbers every time, without inventing values that
have no basis in real data.

Run standalone: uvicorn data_service.app:app --port 8100
"""
import json
import random
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

FLIGHT_SEED_PATH = Path(__file__).parent / "seed_data" / "flight_stats.json"
HOTEL_SEED_PATH = Path(__file__).parent / "seed_data" / "hotel_stats.json"
ACTIVITY_SEED_PATH = Path(__file__).parent / "seed_data" / "activity_fees.json"

_flight_stats: dict[str, list[dict]] = {}
_hotel_price_stats: dict[str, list[dict]] = {}
_hotel_names: dict[str, list[dict]] = {}
_activity_fees: dict[str, list[dict]] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _flight_stats, _hotel_price_stats, _hotel_names, _activity_fees
    with open(FLIGHT_SEED_PATH) as f:
        _flight_stats = json.load(f)
    with open(HOTEL_SEED_PATH) as f:
        hotel_data = json.load(f)
        _hotel_price_stats = hotel_data["price_stats"]
        _hotel_names = hotel_data["hotel_names"]
    with open(ACTIVITY_SEED_PATH) as f:
        _activity_fees = json.load(f)["cities"]
    yield


app = FastAPI(title="TripSync Own Travel Data Service", version="0.2.0", lifespan=lifespan)


class FlightResult(BaseModel):
    airline: str
    flight_number: str
    departure_time: datetime
    arrival_time: datetime
    price: float
    stops: int
    travel_class: str
    data_basis: str = "sampled from real 2022 India domestic fare distribution"


class HotelResult(BaseModel):
    name: str
    area: str
    price_per_night: float
    total_price: float
    rating: float | None
    amenities: list[str]
    data_basis: str = "sampled from real AtliQ Grands booking distribution"


class ActivityResult(BaseModel):
    name: str
    category: str
    estimated_cost: float
    duration_hours: float
    data_basis: str = "real published entry fee (ASI/museum), not sampled"


AIRLINE_CODES = {
    "AirAsia": "I5", "Air_India": "AI", "GO_FIRST": "G8",
    "Indigo": "6E", "SpiceJet": "SG", "Vistara": "UK",
}

# The AtliQ dataset doesn't include neighborhood-level location data,
# only city. This is a clearly-labeled synthetic embellishment layered
# on top of real price/name/rating data, not itself claimed as real.
AREA_POOL = ["City Center", "Business District", "Near Airport", "Old Town", "Uptown"]


def _sample_value(mean: float, std: float, min_val: float, max_val: float) -> float:
    if std <= 0:
        return round(mean, 2)
    sampled = random.gauss(mean, std)
    return round(max(min_val, min(sampled, max_val)), 2)


@app.get("/flights/search", response_model=list[FlightResult])
def search_flights(
    origin: str = Query(..., description="Source city, e.g. 'Delhi'"),
    destination: str = Query(..., description="Destination city, e.g. 'Mumbai'"),
    departure_date: date = Query(..., description="Departure date, YYYY-MM-DD"),
    travel_class: str = Query("Economy", pattern="^(Economy|Business)$"),
    limit: int = Query(5, ge=1, le=10),
):
    route_key = f"{origin.strip().title()}->{destination.strip().title()}"
    combos = _flight_stats.get(route_key)

    if not combos:
        raise HTTPException(
            status_code=404,
            detail=f"No pricing data for route '{route_key}'. "
                   f"This service only covers routes between major Indian metros "
                   f"present in the seed dataset (Delhi, Mumbai, Bangalore, "
                   f"Kolkata, Hyderabad, Chennai).",
        )

    class_combos = [c for c in combos if c["class"] == travel_class]
    if not class_combos:
        raise HTTPException(status_code=404, detail=f"No '{travel_class}' fares for route '{route_key}'.")

    # Prefer combos with more real samples backing them (more trustworthy
    # statistics), cap at `limit` distinct airlines.
    class_combos = sorted(class_combos, key=lambda c: c["sample_count"], reverse=True)[:limit]

    base_departure = datetime.combine(departure_date, datetime.min.time()) + timedelta(
        hours=random.uniform(5, 22)
    )

    results = []
    for combo in class_combos:
        price = _sample_value(combo["mean_price"], combo["std_price"], combo["min_price"], combo["max_price"])
        duration_hours = combo["mean_duration_hours"]
        departure = base_departure + timedelta(minutes=random.randint(0, 180))
        arrival = departure + timedelta(hours=duration_hours)
        code = AIRLINE_CODES.get(combo["airline"], "XX")

        results.append(FlightResult(
            airline=combo["airline"].replace("_", " "),
            flight_number=f"{code}{random.randint(100, 999)}",
            departure_time=departure,
            arrival_time=arrival,
            price=price,
            stops=0 if duration_hours < 3 else random.choice([0, 1]),
            travel_class=travel_class,
        ))

    return results


@app.get("/hotels/search", response_model=list[HotelResult])
def search_hotels(
    city: str = Query(..., description="City, e.g. 'Mumbai'"),
    nights: int = Query(1, ge=1, description="Length of stay in nights"),
    room_class: str | None = Query(
        None, description="Filter to one room class (Standard/Elite/Premium/Presidential); omit for all"
    ),
    limit: int = Query(5, ge=1, le=10),
):
    city_key = city.strip().title()
    price_combos = _hotel_price_stats.get(city_key)
    real_hotels = _hotel_names.get(city_key)

    if not price_combos or not real_hotels:
        raise HTTPException(
            status_code=404,
            detail=f"No pricing data for city '{city_key}'. "
                   f"This service only covers Indian metros present in the "
                   f"seed dataset (Delhi, Mumbai, Bangalore, Hyderabad).",
        )

    if room_class:
        price_combos = [c for c in price_combos if c["room_class"] == room_class]
        if not price_combos:
            raise HTTPException(status_code=404, detail=f"No '{room_class}' room data for '{city_key}'.")

    results = []
    for i, combo in enumerate(price_combos[:limit]):
        price_per_night = _sample_value(
            combo["mean_price_per_night"], combo["std_price_per_night"],
            combo["min_price_per_night"], combo["max_price_per_night"],
        )
        hotel = real_hotels[i % len(real_hotels)]  # cycle through real hotel names
        # Prefer the real per-hotel rating when available; fall back to
        # the real per-room-class average rating for that city.
        rating = hotel.get("rating") or combo.get("mean_rating")

        results.append(HotelResult(
            name=hotel["name"],
            area=random.choice(AREA_POOL),
            price_per_night=price_per_night,
            total_price=round(price_per_night * nights, 2),
            rating=rating,
            amenities=combo["amenities"],
        ))

    return results


@app.get("/activities/search", response_model=list[ActivityResult])
def search_activities(
    city: str = Query(..., description="City, e.g. 'Delhi'"),
    category: str | None = Query(None, description="Filter by category, e.g. 'history'; omit for all"),
    limit: int = Query(5, ge=1, le=10),
):
    """
    Unlike flights/hotels, this returns real fixed published fees, not
    statistically sampled values — there's no transaction-volume dataset
    to derive a distribution from, just point values from ASI/museum
    sources. Coverage is intentionally narrow: only fee-gated
    historical/cultural sites in 4 cities. Anything else (beaches,
    nightlife, food, nature in most cities) correctly 404s so the
    activity agent falls through to Google Places or mock.
    """
    city_key = city.strip().title()
    entries = _activity_fees.get(city_key)

    if not entries:
        raise HTTPException(
            status_code=404,
            detail=f"No real activity fee data for city '{city_key}'. "
                    f"This service only covers a curated set of fee-gated "
                    f"monuments/museums in Delhi, Mumbai, Bangalore, Hyderabad.",
        )

    if category:
        entries = [e for e in entries if e["category"] == category]
        if not entries:
            raise HTTPException(status_code=404, detail=f"No '{category}' activities for '{city_key}'.")

    return [
        ActivityResult(
            name=e["name"],
            category=e["category"],
            estimated_cost=float(e["entry_fee_inr"]),
            duration_hours=e["duration_hours"],
        )
        for e in entries[:limit]
    ]


@app.get("/routes")
def list_routes():
    """Lists all flight routes, hotel cities, and activity cities this service has real data for."""
    return {
        "flight_routes": sorted(_flight_stats.keys()),
        "hotel_cities": sorted(_hotel_price_stats.keys()),
        "activity_cities": sorted(_activity_fees.keys()),
    }


@app.get("/health")
def health():
    return {
        "status": "ok",
        "flight_routes_loaded": len(_flight_stats),
        "hotel_cities_loaded": len(_hotel_price_stats),
        "activity_cities_loaded": len(_activity_fees),
    }
