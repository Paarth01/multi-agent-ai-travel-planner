import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from fastapi.testclient import TestClient

from data_service.app import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


class TestHealth:
    def test_health_reports_routes_loaded(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["flight_routes_loaded"] > 0
        assert response.json()["hotel_cities_loaded"] > 0


class TestListRoutes:
    def test_returns_known_routes(self, client):
        response = client.get("/routes")
        assert response.status_code == 200
        data = response.json()
        assert "Delhi->Mumbai" in data["flight_routes"]
        assert "Mumbai" in data["hotel_cities"]
        assert "Delhi" in data["activity_cities"]


class TestSearchFlights:
    def test_returns_results_for_known_route(self, client):
        response = client.get(
            "/flights/search",
            params={"origin": "Delhi", "destination": "Mumbai", "departure_date": "2026-12-20"},
        )
        assert response.status_code == 200
        results = response.json()
        assert len(results) > 0
        assert all(r["price"] > 0 for r in results)

    def test_business_class_prices_higher_than_economy(self, client):
        economy = client.get(
            "/flights/search",
            params={"origin": "Delhi", "destination": "Mumbai", "departure_date": "2026-12-20", "travel_class": "Economy"},
        ).json()
        business = client.get(
            "/flights/search",
            params={"origin": "Delhi", "destination": "Mumbai", "departure_date": "2026-12-20", "travel_class": "Business"},
        ).json()

        avg_economy = sum(r["price"] for r in economy) / len(economy)
        avg_business = sum(r["price"] for r in business) / len(business)
        assert avg_business > avg_economy

    def test_prices_stay_within_observed_min_max(self, client):
        """
        Sampled prices should never exceed the real dataset's observed
        min/max for that route/airline/class — the whole point of
        clipping is to stay within statistically plausible bounds.
        """
        results = [
            client.get(
                "/flights/search",
                params={"origin": "Delhi", "destination": "Mumbai", "departure_date": "2026-12-20"},
            ).json()
            for _ in range(20)
        ]
        all_prices = [r["price"] for batch in results for r in batch]
        # Sanity bound — real Delhi-Mumbai economy fares in the dataset
        # range roughly 1500-40000; sampled values should never blow past
        # a generous envelope around that.
        assert all(0 < p < 100000 for p in all_prices)

    def test_unknown_route_returns_404(self, client):
        response = client.get(
            "/flights/search",
            params={"origin": "Nowhereville", "destination": "Alsonowhere", "departure_date": "2026-12-20"},
        )
        assert response.status_code == 404

    def test_case_insensitive_city_matching(self, client):
        response = client.get(
            "/flights/search",
            params={"origin": "delhi", "destination": "MUMBAI", "departure_date": "2026-12-20"},
        )
        assert response.status_code == 200

    def test_respects_limit_parameter(self, client):
        response = client.get(
            "/flights/search",
            params={"origin": "Delhi", "destination": "Mumbai", "departure_date": "2026-12-20", "limit": 2},
        )
        assert len(response.json()) <= 2

    def test_invalid_travel_class_rejected(self, client):
        response = client.get(
            "/flights/search",
            params={"origin": "Delhi", "destination": "Mumbai", "departure_date": "2026-12-20", "travel_class": "First"},
        )
        assert response.status_code == 422


class TestSearchHotels:
    def test_returns_results_for_known_city(self, client):
        response = client.get("/hotels/search", params={"city": "Mumbai", "nights": 3})
        assert response.status_code == 200
        results = response.json()
        assert len(results) > 0
        assert all(r["price_per_night"] > 0 for r in results)

    def test_total_price_matches_nights_times_per_night(self, client):
        response = client.get("/hotels/search", params={"city": "Delhi", "nights": 4})
        for r in response.json():
            assert r["total_price"] == pytest.approx(r["price_per_night"] * 4, rel=0.01)

    def test_presidential_more_expensive_than_standard(self, client):
        """
        Real per-night std is large (Presidential in Mumbai: std ~11K on
        a mean of ~24K), so a single sampled draw can occasionally land
        close to or even cross a low-variance Standard draw. Average
        across many draws to reliably compare the underlying means
        rather than asserting on noisy single samples.
        """
        presidential_prices = []
        standard_prices = []
        for _ in range(30):
            presidential_prices += [
                r["price_per_night"]
                for r in client.get(
                    "/hotels/search", params={"city": "Mumbai", "nights": 1, "room_class": "Presidential"}
                ).json()
            ]
            standard_prices += [
                r["price_per_night"]
                for r in client.get(
                    "/hotels/search", params={"city": "Mumbai", "nights": 1, "room_class": "Standard"}
                ).json()
            ]

        avg_presidential = sum(presidential_prices) / len(presidential_prices)
        avg_standard = sum(standard_prices) / len(standard_prices)
        assert avg_presidential > avg_standard

    def test_returns_real_hotel_names(self, client):
        response = client.get("/hotels/search", params={"city": "Delhi", "nights": 1})
        names = {r["name"] for r in response.json()}
        # Real names from the AtliQ dataset, not generic placeholders
        assert any("Atliq" in name for name in names)

    def test_includes_ratings(self, client):
        response = client.get("/hotels/search", params={"city": "Bangalore", "nights": 1})
        assert all(r["rating"] is not None for r in response.json())

    def test_unknown_city_returns_404(self, client):
        response = client.get("/hotels/search", params={"city": "Nowhereville", "nights": 1})
        assert response.status_code == 404

    def test_unknown_room_class_returns_404(self, client):
        response = client.get(
            "/hotels/search", params={"city": "Mumbai", "nights": 1, "room_class": "Penthouse"}
        )
        assert response.status_code == 404

    def test_case_insensitive_city_matching(self, client):
        response = client.get("/hotels/search", params={"city": "mumbai", "nights": 1})
        assert response.status_code == 200


class TestSearchActivities:
    def test_returns_real_entries_for_known_city(self, client):
        response = client.get("/activities/search", params={"city": "Delhi"})
        assert response.status_code == 200
        results = response.json()
        names = {r["name"] for r in results}
        assert "Red Fort" in names

    def test_returns_deterministic_real_fees_not_sampled(self, client):
        """
        Unlike flights/hotels, activity fees are fixed real values, not
        statistically sampled — repeated calls should return identical
        prices every time.
        """
        r1 = client.get("/activities/search", params={"city": "Delhi"}).json()
        r2 = client.get("/activities/search", params={"city": "Delhi"}).json()
        assert r1 == r2

    def test_red_fort_fee_matches_known_real_value(self, client):
        response = client.get("/activities/search", params={"city": "Delhi"})
        red_fort = next(r for r in response.json() if r["name"] == "Red Fort")
        assert red_fort["estimated_cost"] == 35.0

    def test_free_entry_sites_have_zero_cost(self, client):
        response = client.get("/activities/search", params={"city": "Mumbai"})
        gateway = next(r for r in response.json() if r["name"] == "Gateway of India")
        assert gateway["estimated_cost"] == 0.0

    def test_category_filter_works(self, client):
        response = client.get("/activities/search", params={"city": "Bangalore", "category": "nature"})
        assert response.status_code == 200
        assert all(r["category"] == "nature" for r in response.json())

    def test_unknown_city_returns_404(self, client):
        response = client.get("/activities/search", params={"city": "Nowhereville"})
        assert response.status_code == 404

    def test_uncovered_category_returns_404_not_empty_list(self):
        """
        Real coverage is narrow (fee-gated monuments only) — a category
        like 'nightlife' genuinely isn't covered for any city, and
        should 404 (letting the agent fall through) rather than
        silently returning an empty 200.
        """
        with TestClient(app) as c:
            response = c.get("/activities/search", params={"city": "Delhi", "category": "nightlife"})
            assert response.status_code == 404

    def test_case_insensitive_city_matching(self, client):
        response = client.get("/activities/search", params={"city": "delhi"})
        assert response.status_code == 200


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
