import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from storage import ItineraryStore

@pytest.fixture
def store(tmp_path):
    db_path = str(tmp_path / "test.db")
    s = ItineraryStore(db_path=db_path)
    yield s
    s.close()


def test_save_and_get(store):
    dummy = {
        "trip_request": {
            "destination": "Goa",
            "origin": "Delhi",
            "start_date": "2026-12-20",
            "end_date": "2026-12-25"
        },
        "total_cost": 40000.0,
        "best_effort": False,
        "flight": {"airline": "Vistara"}
    }
    trip_id = store.save(dummy)
    assert trip_id is not None
    assert len(trip_id) == 12

    retrieved = store.get(trip_id)
    assert retrieved is not None
    assert retrieved["id"] == trip_id
    assert retrieved["trip_request"]["destination"] == "Goa"
    assert retrieved["flight"]["airline"] == "Vistara"


def test_get_not_found(store):
    assert store.get("does_not_exist") is None


def test_list_all(store):
    store.save({
        "trip_request": {"destination": "Goa"},
        "total_cost": 100.0
    })
    store.save({
        "trip_request": {"destination": "Mumbai"},
        "total_cost": 200.0
    })

    trips = store.list_all()
    assert len(trips) == 2
    # newest first
    assert trips[0]["destination"] == "Mumbai"
    assert trips[1]["destination"] == "Goa"


def test_delete(store):
    trip_id = store.save({
        "trip_request": {"destination": "Goa"}
    })
    
    assert store.delete(trip_id) is True
    assert store.get(trip_id) is None
    
    # second delete should return False
    assert store.delete(trip_id) is False
