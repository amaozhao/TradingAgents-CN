from __future__ import annotations

from fastapi.routing import APIRoute

from app.routers.analysis import router


def _registered_http_routes() -> set[tuple[str, str]]:
    routes: set[tuple[str, str]] = set()
    for route in router.routes:
        if isinstance(route, APIRoute):
            for method in route.methods or set():
                routes.add((method, route.path))
    return routes


def test_analysis_router_keeps_task_list_and_batch_routes() -> None:
    routes = _registered_http_routes()

    assert ("GET", "/tasks") in routes
    assert ("GET", "/tasks/all") in routes
    assert ("POST", "/batch") in routes
