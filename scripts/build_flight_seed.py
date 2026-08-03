"""
One-time script: aggregates the raw Kaggle "Flight Price Prediction"
dataset (Clean_Dataset.csv, ~300K rows, real 2022 Indian domestic
fares — https://www.kaggle.com/datasets/shubhambathwal/flight-price-prediction)
into compact per-route/airline/class statistics.

We don't ship the 24MB raw CSV in the repo — instead this produces a
~50KB JSON of (route, airline, class) -> {mean, std, min, max, count,
mean_duration} that data_service/app.py samples from at request time.
This keeps real statistical shape (actual route pricing, actual
airline pricing spread) without bundling raw data or needing pandas
as a runtime dependency for the service itself.

Usage:
    python scripts/build_flight_seed.py path/to/Clean_Dataset.csv
"""
import json
import sys
from pathlib import Path

import pandas as pd

OUTPUT_PATH = Path(__file__).parent.parent / "data_service" / "seed_data" / "flight_stats.json"


def build_seed(csv_path: str) -> None:
    df = pd.read_csv(csv_path)

    grouped = df.groupby(["source_city", "destination_city", "airline", "class"]).agg(
        mean_price=("price", "mean"),
        std_price=("price", "std"),
        min_price=("price", "min"),
        max_price=("price", "max"),
        mean_duration=("duration", "mean"),
        count=("price", "count"),
    ).reset_index()

    # Only keep route/airline/class combos with enough samples to trust
    # the statistics (avoids single-flight outliers skewing the sampler).
    grouped = grouped[grouped["count"] >= 20]

    stats = {}
    for _, row in grouped.iterrows():
        route_key = f"{row['source_city']}->{row['destination_city']}"
        stats.setdefault(route_key, []).append({
            "airline": row["airline"],
            "class": row["class"],
            "mean_price": round(float(row["mean_price"]), 2),
            "std_price": round(float(row["std_price"]), 2) if pd.notna(row["std_price"]) else 0.0,
            "min_price": round(float(row["min_price"]), 2),
            "max_price": round(float(row["max_price"]), 2),
            "mean_duration_hours": round(float(row["mean_duration"]), 2),
            "sample_count": int(row["count"]),
        })

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(stats, f, indent=2)

    print(f"Wrote {len(stats)} routes, {sum(len(v) for v in stats.values())} route/airline/class combos")
    print(f"-> {OUTPUT_PATH} ({OUTPUT_PATH.stat().st_size / 1024:.1f} KB)")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python scripts/build_flight_seed.py path/to/Clean_Dataset.csv")
        sys.exit(1)
    build_seed(sys.argv[1])
