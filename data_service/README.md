# Own Travel Data Service

A self-hosted microservice that serves realistic flight, hotel, and
activity search results — no third-party API, no rate limits, no
credentials.

## How it works

**Flights**: `seed_data/flight_stats.json` holds real per-route/airline/
class pricing statistics derived from the Kaggle
["Flight Price Prediction"](https://www.kaggle.com/datasets/shubhambathwal/flight-price-prediction)
dataset — ~300K rows of real 2022 Indian domestic fares across 6 metro
cities (Delhi, Mumbai, Bangalore, Kolkata, Hyderabad, Chennai).

**Hotels**: `seed_data/hotel_stats.json` holds real per-city/room-class
per-night pricing statistics, real hotel names, and real customer
ratings derived from the "AtliQ Grands" hotel booking dataset — ~134K
real bookings across 4 metro cities (Delhi, Mumbai, Bangalore,
Hyderabad), mirrored on GitHub at
[SahilChipkar/AtliQ-Grands-Hotel-Analysis](https://github.com/SahilChipkar/AtliQ-Grands-Hotel-Analysis).

**Activities**: `seed_data/activity_fees.json` holds real, **hand-curated**
entry fees for fee-gated monuments/museums — sourced from ASI
(Archaeological Survey of India) official pricing and museum-published
rates, cross-referenced across multiple sources. This is fundamentally
different from the flight/hotel data: there's no bulk transaction
dataset for attraction visits the way there is for bookings, so this
was manually compiled rather than aggregated. Coverage is intentionally
narrow — only `history`/`nature` category sites in 4 cities. See the
`_source_note` field in the JSON file for the full caveat, including
that some sources disagreed by 2-3x on the same site's fee.

At request time, `app.py` samples a fresh value from the real
distribution for flights/hotels (a normal distribution parameterized
by the actual observed mean/std, clipped to the actual observed
min/max) — so repeated searches vary realistically instead of
returning identical numbers every time. **Activities are different**:
they return the real fixed published fee every time, since there's no
distribution to sample from, just point values.

## Running it

```bash
uvicorn data_service.app:app --port 8100 --reload
```

Then point the main app at it via `.env`:
```
OWN_FLIGHT_SERVICE_URL=http://localhost:8100
OWN_HOTEL_SERVICE_URL=http://localhost:8100
OWN_ACTIVITY_SERVICE_URL=http://localhost:8100
```

`graph/flight_agent.py`, `graph/hotel_agent.py`, and
`graph/activity_agent.py` each try this service first (tier 1), fall
back to Amadeus/Google Places if configured (tier 2), then mock data
(tier 3) — see each file's module docstring. The activity agent has an
extra nuance: it filters the own service's real results against the
user's stated interests locally, and treats "real data exists for this
city but none of it matches what the user asked for" as a miss that
falls through to the next tier, rather than returning an irrelevant
result just because the service technically responded.

## Regenerating the seed data

Raw datasets aren't checked into this repo (24MB flight CSV, ~5MB hotel
CSVs — not great git hygiene). Activities have no raw dataset to
regenerate from — `activity_fees.json` is the source of truth, edited
by hand.

**Flights**: download `Clean_Dataset.csv` from the Kaggle link above
(or find a GitHub mirror — several exist), then:
```bash
python scripts/build_flight_seed.py path/to/Clean_Dataset.csv
```

**Hotels**: clone or download `dim_hotels.csv`, `dim_rooms.csv`, and
`fact_bookings.csv` from the GitHub repo above (or any mirror of the
same "AtliQ Grands" dataset — it's a common one in Indian data
analytics coursework), then:
```bash
python scripts/build_hotel_seed.py path/to/datasets_dir
```

**Activities**: edit `seed_data/activity_fees.json` directly. To add a
city or site, verify the fee against the site's official source (ASI
website, museum's own site) rather than a single travel-blog aggregator
— several were found to disagree significantly during research.

## Known limitations

- **Coverage**: flights cover 6 metro cities, hotels cover 4, activities
  cover 4 cities but only 2 categories (`history`, `nature`) — nothing
  for beaches/nightlife/food anywhere, since fee-gated venues in those
  categories are rare (beach access is free, restaurant/club entry
  isn't fee-ticketed the way monuments are). Cities/categories outside
  coverage return 404, which the agents correctly treat as "no
  coverage, try the next tier."
- **Stale by construction**: flight fares are from 2022, hotel prices
  are from a ~3-month historical window, activity fees are current as
  of early-mid 2026 research but not live — all sampled/fixed, not
  real-time pricing. Fine for a demo; don't use this for actual
  trip-planning decisions.
- **No date sensitivity**: real flight/hotel prices vary by season, day
  of week, days-until-booking — none of which this samples on.
- **Hotel `area` (neighborhood) is synthetic**: the source dataset only
  has city-level location, not neighborhood — `area` is randomly
  assigned from a generic pool (`City Center`, `Business District`,
  etc.), clearly separate from the real name/price/rating fields.
- **Activity fee accuracy**: hand-curated from web sources as of
  research time, not a live feed — entry fees do change periodically
  (the CSMVS museum fee alone was quoted anywhere from ₹60 to ₹200
  across different sources). Re-verify before relying on these for
  anything beyond a demo.
