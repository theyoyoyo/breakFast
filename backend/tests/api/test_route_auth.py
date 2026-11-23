"""Login on every route: the test walks the app's route table, so a new route is covered without
editing it, and only the routes in PUBLIC may answer without a valid login."""

import re

import aiosqlite
import pytest
from fastapi.routing import APIRoute, APIWebSocketRoute
from httpx import ASGITransport, AsyncClient
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

import database
from auth import create_token, revoke_token
from main import app

# The only routes that answer without a valid login, each with its reason
PUBLIC = {
    ("POST", "/auth/login"): "logging in is how a token is got",
    ("POST", "/auth/logout"): "ends the session it is sent with; an unknown or ended one gets 204 too, so logging out twice is harmless",
    ("GET", "/health"): "says the server is up, for start scripts and monitors; returns no data",
}
# Public too, but only in the app when SERVE_FRONTEND=true or API_DOCS=true, which the tests turn off
PUBLIC_WHEN_ENABLED = {
    ("GET", "/{full_path:path}"): "the built frontend: index.html for any other path (SERVE_FRONTEND)",
    ("Mount", "/assets"): "the built frontend's static files (SERVE_FRONTEND)",
    ("Route", "/openapi.json"): "the API schema (API_DOCS)",
    ("Route", "/docs"): "the API docs (API_DOCS)",
    ("Route", "/docs/oauth2-redirect"): "the API docs (API_DOCS)",
    ("Route", "/redoc"): "the API docs (API_DOCS)",
}


async def _bad_headers():
    """Each way a request can lack a valid login: no header, malformed ones, an unknown token and a logged-out one."""
    async with aiosqlite.connect(database.DATABASE_PATH) as db:
        async with db.execute("SELECT id FROM users LIMIT 1") as cur:
            user_id = (await cur.fetchone())[0]
    revoked = create_token(user_id)
    revoke_token(revoked)
    return {
        "no header": None,
        "not bearer": f"Token {create_token(user_id)}",
        "empty bearer": "Bearer ",
        "unknown token": "Bearer not-a-real-token",
        "logged out": f"Bearer {revoked}",
    }


async def _snapshot():
    """Every row of every table, to show a refused request saved nothing."""
    async with aiosqlite.connect(database.DATABASE_PATH) as db:
        async with db.execute("SELECT name FROM sqlite_master WHERE type = 'table'") as cur:
            tables = [r[0] for r in await cur.fetchall()]
        snapshot = {}
        for table in tables:
            async with db.execute(f"SELECT * FROM {table}") as cur:  # noqa: S608 (names from sqlite_master)
                snapshot[table] = sorted(map(repr, await cur.fetchall()))
    return snapshot


def _endpoints():
    """Every (method, path) in the app's route table, sockets as ("WS", path)."""
    endpoints = []
    for route in app.routes:
        if isinstance(route, APIRoute):
            endpoints += [(method, route.path) for method in sorted(route.methods - {"HEAD", "OPTIONS"})]
        elif isinstance(route, APIWebSocketRoute):
            endpoints.append(("WS", route.path))
        else:
            endpoints.append((type(route).__name__, route.path))
    return endpoints


# Every route but the public ones refuses a request with no login, a malformed one, an unknown token or a logged-out one, and saves nothing
async def test_every_route_requires_login(client):
    bad_headers = await _bad_headers()
    before = await _snapshot()
    checked = []
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as bare:
        for method, path in _endpoints():
            if (method, path) in PUBLIC or (method, path) in PUBLIC_WHEN_ENABLED:
                continue
            url = re.sub(r"{[^}]+}", "1", path)
            for case, header in bad_headers.items():
                if method == "WS":
                    protocols = None if header is None else ["bearer", header.removeprefix("Bearer ")]
                    try:
                        with TestClient(app).websocket_connect(url, subprotocols=protocols):
                            code = None
                    except WebSocketDisconnect as exc:
                        code = exc.code
                    assert code == 4001, f"{method} {path} with {case}: socket opened"
                    continue
                assert method in {"GET", "POST", "PUT", "PATCH", "DELETE"}, f"unknown route type {method} {path}"
                headers = {} if header is None else {"Authorization": header}
                r = await bare.request(method, url, headers=headers, json={})
                if header is None:
                    # The missing header is refused before anything runs (422, naming the header)
                    assert r.status_code == 422, f"{method} {path} with {case}: {r.status_code}"
                    assert ["header", "Authorization"] in [e["loc"] for e in r.json()["detail"]], f"{method} {path}"
                else:
                    assert r.status_code == 401, f"{method} {path} with {case}: {r.status_code}"
            checked.append((method, path))
    assert await _snapshot() == before
    assert len(checked) > 60 and ("WS", "/chat") in checked


# Each public route is still in the app, so the list of exceptions can't keep a route that's gone
def test_public_routes_exist():
    assert set(PUBLIC) <= set(_endpoints())


# The public routes answer without a login, as their reasons say
async def test_public_routes_answer_without_login(client):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as bare:
        assert (await bare.get("/health")).status_code == 200
        assert (await bare.post("/auth/logout")).status_code == 204
        assert (await bare.post("/auth/login", json={"name": "testuser", "pin": "1234"})).status_code == 200


# A valid login still opens a protected route, so the sweep's refusals come from the login check and not a broken route
@pytest.mark.parametrize("path", ["/health/auth", "/meals/"])
async def test_valid_login_opens_protected_routes(client, path):
    assert (await client.get(path)).status_code == 200
