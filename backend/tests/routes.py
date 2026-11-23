"""The app's real endpoints for the tests that sweep the route table.

Newer FastAPI keeps each included router as one wrapper entry in `app.routes` instead of listing its
routes, so a loop over `app.routes` would see no endpoints (or fail on the wrapper's missing `path`).
`endpoints()` gives the same list on both: wrappers are opened, and each endpoint carries its full
path (the include prefix applied), its methods and its original route."""

from typing import NamedTuple

from fastapi.routing import APIRoute, APIWebSocketRoute

try:  # FastAPI with included-router wrappers
    from fastapi.routing import iter_route_contexts
except ImportError:  # older FastAPI: app.routes is already flat
    iter_route_contexts = None


class Endpoint(NamedTuple):
    path: str
    methods: frozenset  # empty for a socket or a mount
    route: object  # the route as the app declared it (APIRoute, APIWebSocketRoute, Route, Mount…)


def endpoints(app):
    """Every route the app serves: APIRoute and APIWebSocketRoute entries and any other route (docs, mounts)."""
    if iter_route_contexts is None:
        return [Endpoint(r.path, frozenset(getattr(r, "methods", None) or ()), r) for r in app.routes]
    return [Endpoint(c.path, frozenset(c.methods or ()), c.original_route) for c in iter_route_contexts(app.routes)]


def api_endpoints(app):
    """Only the HTTP API routes."""
    return [e for e in endpoints(app) if isinstance(e.route, APIRoute)]


def socket_endpoints(app):
    """Only the WebSocket routes."""
    return [e for e in endpoints(app) if isinstance(e.route, APIWebSocketRoute)]
