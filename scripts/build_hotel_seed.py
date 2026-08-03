"""
One-time script: aggregates the real "AtliQ Grands" Indian hotel
booking dataset (dim_hotels.csv, dim_rooms.csv, fact_bookings.csv —
~134K real bookings across 4 Indian metro cities, a well-known dataset
used in Indian data-analytics coursework, mirrored on GitHub, e.g.
https://github.com/SahilChipkar/AtliQ-Grands-Hotel-Analysis/tree/main/datasets)
into compact per-city/room-class per-night price statistics.

Mirrors the same approach as scripts/build_flight_seed.py: real
statistical shape (actual per-night rates by city and room class),
without bundling ~5MB of raw booking rows.

Usage:
    python scripts/build_hotel_seed.py path/to/datasets_dir
    (expects dim_hotels.csv, dim_rooms.csv, fact_bookings.csv in that dir)
"""
import json
import sys
from pathlib import Path

import pandas as pd

OUTPUT_PATH = Path(__file__).parent.parent / "data_service" / "seed_data" / "hotel_stats.json"

ROOM_AMENITIES = {
    "Standard": ["wifi", "breakfast"],
    "Elite": ["wifi", "breakfast", "gym"],
    "Premium": ["wifi", "breakfast", "gym", "pool"],
    "Presidential": ["wifi", "breakfast", "gym", "pool", "spa", "parking"],
}


def build_seed(datasets_dir: str) -> None:
    datasets_dir = Path(datasets_dir)
    hotels = pd.read_csv(datasets_dir / "dim_hotels.csv")
    rooms = pd.read_csv(datasets_dir / "dim_rooms.csv")
    bookings = pd.read_csv(datasets_dir / "fact_bookings.csv")

    bookings["check_in_date"] = pd.to_datetime(bookings["check_in_date"], format="%d/%m/%Y", errors="coerce")
    bookings["checkout_date"] = pd.to_datetime(bookings["checkout_date"], format="%d/%m/%Y", errors="coerce")
    bookings["nights"] = (bookings["checkout_date"] - bookings["check_in_date"]).dt.days

    # Only completed stays with valid, positive night counts — cancelled/
    # no-show bookings don't reflect an actual price paid for a stay.
    bookings = bookings[(bookings["booking_status"] == "Checked Out") & (bookings["nights"] > 0)]
    bookings["price_per_night"] = bookings["revenue_realized"] / bookings["nights"]

    merged = bookings.merge(hotels, on="property_id").merge(rooms, left_on="room_category", right_on="room_id")

    grouped = merged.groupby(["city", "room_class"]).agg(
        mean_price=("price_per_night", "mean"),
        std_price=("price_per_night", "std"),
        min_price=("price_per_night", "min"),
        max_price=("price_per_night", "max"),
        mean_rating=("ratings_given", "mean"),  # real customer ratings, ~42% of bookings have one
        count=("price_per_night", "count"),
    ).reset_index()

    stats: dict[str, list[dict]] = {}
    for _, row in grouped.iterrows():
        city = row["city"]
        stats.setdefault(city, []).append({
            "room_class": row["room_class"],
            "mean_price_per_night": round(float(row["mean_price"]), 2),
            "std_price_per_night": round(float(row["std_price"]), 2) if pd.notna(row["std_price"]) else 0.0,
            "min_price_per_night": round(float(row["min_price"]), 2),
            "max_price_per_night": round(float(row["max_price"]), 2),
            "mean_rating": round(float(row["mean_rating"]), 1) if pd.notna(row["mean_rating"]) else None,
            "amenities": ROOM_AMENITIES.get(row["room_class"], ["wifi"]),
            "sample_count": int(row["count"]),
        })

    # Real hotel names + real per-hotel average rating, for realistic
    # display names in results.
    hotel_rating_by_property = merged.groupby("property_id")["ratings_given"].mean()
    hotel_names: dict[str, list[dict]] = {}
    for _, row in hotels.iterrows():
        rating = hotel_rating_by_property.get(row["property_id"])
        hotel_names.setdefault(row["city"], []).append({
            "name": row["property_name"],
            "category": row["category"],
            "rating": round(float(rating), 1) if pd.notna(rating) else None,
        })

    output = {"price_stats": stats, "hotel_names": hotel_names}

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(output, f, indent=2)

    print(f"Wrote stats for {len(stats)} cities, {sum(len(v) for v in stats.values())} city/room-class combos")
    print(f"Wrote {sum(len(v) for v in hotel_names.values())} real hotel names across {len(hotel_names)} cities")
    print(f"-> {OUTPUT_PATH} ({OUTPUT_PATH.stat().st_size / 1024:.1f} KB)")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python scripts/build_hotel_seed.py path/to/datasets_dir")
        sys.exit(1)
    build_seed(sys.argv[1])
