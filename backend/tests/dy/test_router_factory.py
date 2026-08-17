from __future__ import annotations

from fastapi import FastAPI

from app.routers.dy.router_factory import build_dy_router


def current_user():
    return {"id": "00000000-0000-0000-0000-00000000b002", "role": "USER"}


def admin_user():
    return {"id": "00000000-0000-0000-0000-00000000b001", "role": "ADMIN"}


EXPECTED_OPERATIONS = {
    "/airports": {"get"},
    "/flights": {"get", "post"},
    "/flights/{flight_id}": {"get", "put", "delete"},
    "/flights/{flight_id}/seats": {"get", "post"},
    "/admin/flights": {"get"},
    "/seats/{seat_id}": {"put", "delete"},
    "/bookings": {"post"},
    "/bookings/me": {"get"},
    "/bookings/{booking_id}": {"get"},
    "/bookings/{booking_id}/cancel": {"put"},
    "/admin/bookings": {"get"},
    "/admin/bookings/{booking_id}/status": {"put"},
    "/uploads/images": {"post"},
    "/events/stream": {"get"},
    "/admin/event-logs": {"get"},
    "/admin/event-logs/{event_log_id}": {"get"},
    "/feedbacks": {"post"},
    "/admin/feedbacks": {"get"},
    "/admin/feedbacks/{feedback_id}": {"get"},
    "/chat/feedbacks": {"post"},
    "/admin/chat-feedbacks/summary": {"get"},
    "/admin/chat-feedbacks": {"get"},
    "/admin/chat-feedbacks/{feedback_id}": {"get"},
    "/admin/chat-feedbacks/{feedback_id}/review": {"put"},
    "/admin/dashboard": {"get"},
}


def create_openapi(tmp_path) -> dict:
    app = FastAPI()
    app.include_router(
        build_dy_router(current_user, admin_user, upload_dir=tmp_path)
    )
    return app.openapi()


def test_integrated_router_exposes_every_planned_dy_operation(tmp_path) -> None:
    openapi = create_openapi(tmp_path)

    actual = {
        path: {
            method
            for method in path_item
            if method in {"get", "post", "put", "delete", "patch"}
        }
        for path, path_item in openapi["paths"].items()
    }

    assert actual == EXPECTED_OPERATIONS


def test_integrated_router_has_unique_operation_ids(tmp_path) -> None:
    openapi = create_openapi(tmp_path)
    operation_ids = [
        operation["operationId"]
        for path_item in openapi["paths"].values()
        for method, operation in path_item.items()
        if method in {"get", "post", "put", "delete", "patch"}
    ]

    assert len(operation_ids) == len(set(operation_ids))


def test_integrated_router_documents_creation_and_empty_delete_statuses(tmp_path) -> None:
    paths = create_openapi(tmp_path)["paths"]

    assert "201" in paths["/bookings"]["post"]["responses"]
    assert "201" in paths["/feedbacks"]["post"]["responses"]
    assert "201" in paths["/chat/feedbacks"]["post"]["responses"]
    assert "201" in paths["/uploads/images"]["post"]["responses"]
    assert "201" in paths["/flights"]["post"]["responses"]
    assert "201" in paths["/flights/{flight_id}/seats"]["post"]["responses"]
    assert "204" in paths["/flights/{flight_id}"]["delete"]["responses"]
    assert "204" in paths["/seats/{seat_id}"]["delete"]["responses"]


def test_dependencies_are_not_misclassified_as_query_parameters(tmp_path) -> None:
    paths = create_openapi(tmp_path)["paths"]

    for path_item in paths.values():
        for method, operation in path_item.items():
            if method not in {"get", "post", "put", "delete", "patch"}:
                continue
            parameter_names = {
                parameter["name"] for parameter in operation.get("parameters", [])
            }
            assert "principal" not in parameter_names
            assert "_principal" not in parameter_names
            assert "client" not in parameter_names
