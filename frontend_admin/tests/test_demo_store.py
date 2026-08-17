from core.demo_store import SEED


def test_required_feedback_fields_exist():
    required = {"conversation_id", "rating", "question", "answer", "comment", "cause", "memo", "created_at"}
    assert SEED["feedbacks"]
    assert all(required <= item.keys() for item in SEED["feedbacks"])


def test_rating_range_and_low_rating_examples():
    assert all(1 <= item["rating"] <= 5 for item in SEED["feedbacks"])
    assert any(item["rating"] <= 2 for item in SEED["feedbacks"])


def test_event_types_cover_required_monitoring():
    types = {item["type"] for item in SEED["events"]}
    assert {"BOOKING_CREATED", "BOOKING_CANCELLED", "SEAT_CHANGED", "FLIGHT_STATUS_CHANGED"} <= types


def test_admin_management_collections_exist():
    required = {
        "flights",
        "seats",
        "bookings",
        "users",
        "events",
        "feedbacks",
        "service_feedbacks",
    }
    assert required <= SEED.keys()


def test_service_feedback_fields_exist():
    required = {"id", "user_id", "rating", "category", "content", "created_at"}
    assert SEED["service_feedbacks"]
    assert all(required <= item.keys() for item in SEED["service_feedbacks"])


def test_demo_ids_are_unique_per_collection():
    for collection in ("flights", "seats", "bookings", "users", "events"):
        ids = [item["id"] for item in SEED[collection]]
        assert len(ids) == len(set(ids))
