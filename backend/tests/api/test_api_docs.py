"""The API docs and schema routes are served only when API_DOCS is on."""

import importlib

import pytest

DOC_PATHS = ["/docs", "/redoc", "/openapi.json"]




@pytest.fixture
def restore_main():
    """Reload main with the real settings afterwards, so other tests see the normal app."""
    yield
    import main

    importlib.reload(main)


async def _statuses(app):
    from httpx import ASGITransport, AsyncClient

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        return [(await ac.get(p)).status_code for p in DOC_PATHS]


@pytest.mark.asyncio
async def test_docs_routes_are_off_by_default(client, restore_main, monkeypatch):
    """With API_DOCS off, /docs, /redoc and /openapi.json all return 404."""
    import config

    monkeypatch.setattr(config, "API_DOCS", False)
    app = importlib.reload(__import__("main")).app
    assert await _statuses(app) == [404, 404, 404]


@pytest.mark.asyncio
async def test_docs_routes_are_served_when_enabled(client, restore_main, monkeypatch):
    """With API_DOCS on, /docs, /redoc and /openapi.json all return 200."""
    import config

    monkeypatch.setattr(config, "API_DOCS", True)
    app = importlib.reload(__import__("main")).app
    assert await _statuses(app) == [200, 200, 200]
