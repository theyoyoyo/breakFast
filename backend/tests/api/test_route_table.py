"""The helper the route sweeps use finds every endpoint the app serves, so a FastAPI that keeps
routes in wrappers can't make a sweep quietly check fewer of them."""

from main import app
from tests.routes import api_endpoints, endpoints, socket_endpoints


# The helper lists exactly the operations the app's own OpenAPI schema (built by FastAPI from its routes) lists
def test_helper_matches_the_openapi_schema():
    served = {
        (method.lower(), e.path)
        for e in api_endpoints(app)
        if e.route.include_in_schema
        for method in e.methods - {"HEAD", "OPTIONS"}
    }
    documented = {(method, path) for path, operations in app.openapi()["paths"].items() for method in operations}
    assert served == documented
    assert len(served) > 60


# The helper keeps the endpoints every sweep must see, a socket included, and each path starts with its router's prefix
def test_helper_finds_named_endpoints():
    found = {(m, e.path) for e in api_endpoints(app) for m in e.methods}
    assert {("POST", "/auth/login"), ("GET", "/health"), ("GET", "/ingredients/"), ("POST", "/favorites/")} <= found
    assert [e.path for e in socket_endpoints(app)] == ["/chat"]
    assert all(e.path.startswith("/") for e in endpoints(app))
