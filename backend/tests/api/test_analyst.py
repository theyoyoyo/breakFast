"""
Tests for the /analyst endpoint — nutrition analysis REST API.
Mocks the LLM to test endpoint logic without requiring Ollama.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest
from unittest.mock import patch


MOCK_ANALYSIS = (
    "Bu kahvaltı protein açısından zengin.\n\n"
    "```json\n"
    '{"narrative": "Test narrative", "daily_coverage": [], "macros": {"calories_kcal": 400}, "micros": []}\n'
    "```"
)


def _mock_stream_factory(response_text):
    """Create a mock async generator that yields the response in chunks."""
    async def mock_stream(*args, **kwargs):
        for chunk in response_text.split():
            yield chunk + " "
    return mock_stream


# Verifies endpoint returns 200 with mocked LLM response
@pytest.mark.asyncio
async def test_analyze_meal_success(client):
    with patch("routers.analyst.stream_response", side_effect=_mock_stream_factory(MOCK_ANALYSIS)):
        r = await client.post("/analyst/analyze", json={
            "meal_name": "Menemen",
            "ingredients": ["yumurta", "domates", "biber"],
        })

    assert r.status_code == 200
    data = r.json()
    assert "analysis_text" in data
    assert data["analysis_data"] is not None or data["analysis_text"] != ""
    assert data["cached"] is False


# Accepts structured ingredients with quantity and unit
@pytest.mark.asyncio
async def test_analyze_structured_ingredients(client):
    with patch("routers.analyst.stream_response", side_effect=_mock_stream_factory(MOCK_ANALYSIS)):
        r = await client.post("/analyst/analyze", json={
            "meal_name": "Menemen",
            "ingredients": [
                {"name": "yumurta", "quantity": 2, "unit": "adet"},
                {"name": "domates", "quantity": 1, "unit": "adet"},
            ],
        })

    assert r.status_code == 200
    assert r.json()["analysis_data"] is not None


# Caches analysis result when meal_id is provided
@pytest.mark.asyncio
async def test_analyze_caches_result(client):
    meal = (await client.post("/meals/", json={
        "meal_name": "Toast",
        "ingredients": [{"name": "ekmek", "quantity": 2, "unit": "dilim"}],
    })).json()

    with patch("routers.analyst.stream_response", side_effect=_mock_stream_factory(MOCK_ANALYSIS)):
        r = await client.post("/analyst/analyze", json={
            "meal_name": "Toast",
            "ingredients": [{"name": "ekmek", "quantity": 2, "unit": "dilim"}],
            "meal_id": meal["id"],
        })

    assert r.status_code == 200
    assert r.json()["cached"] is False

    # Verify cache was written
    meal_after = (await client.get(f"/meals/{meal['id']}")).json()
    assert meal_after["cached_nutrition"] is not None


# Returns cached result on second call without hitting LLM
@pytest.mark.asyncio
async def test_analyze_returns_cached(client):
    meal = (await client.post("/meals/", json={
        "meal_name": "Toast",
        "ingredients": [{"name": "ekmek", "quantity": 2, "unit": "dilim"}],
    })).json()

    with patch("routers.analyst.stream_response", side_effect=_mock_stream_factory(MOCK_ANALYSIS)):
        await client.post("/analyst/analyze", json={
            "meal_name": "Toast",
            "ingredients": [{"name": "ekmek", "quantity": 2, "unit": "dilim"}],
            "meal_id": meal["id"],
        })

    # Second call should return cached — no LLM mock needed
    r = await client.post("/analyst/analyze", json={
        "meal_name": "Toast",
        "ingredients": [{"name": "ekmek", "quantity": 2, "unit": "dilim"}],
        "meal_id": meal["id"],
    })

    assert r.status_code == 200
    assert r.json()["cached"] is True


# Updating a meal clears the cache, next analysis recalculates
@pytest.mark.asyncio
async def test_update_clears_cache_then_reanalyze(client):
    meal = (await client.post("/meals/", json={
        "meal_name": "Toast",
        "ingredients": [{"name": "ekmek", "quantity": 2, "unit": "dilim"}],
    })).json()

    with patch("routers.analyst.stream_response", side_effect=_mock_stream_factory(MOCK_ANALYSIS)):
        await client.post("/analyst/analyze", json={
            "meal_name": "Toast",
            "ingredients": [{"name": "ekmek", "quantity": 2, "unit": "dilim"}],
            "meal_id": meal["id"],
        })

    # Update meal — clears cache
    await client.put(f"/meals/{meal['id']}", json={
        "meal_name": "Toast",
        "ingredients": [{"name": "ekmek", "quantity": 3, "unit": "dilim"}],
    })

    # Verify cache is cleared
    meal_after = (await client.get(f"/meals/{meal['id']}")).json()
    assert meal_after["cached_nutrition"] is None

    # Re-analyze should hit LLM again
    with patch("routers.analyst.stream_response", side_effect=_mock_stream_factory(MOCK_ANALYSIS)) as mock:
        r = await client.post("/analyst/analyze", json={
            "meal_name": "Toast",
            "ingredients": [{"name": "ekmek", "quantity": 3, "unit": "dilim"}],
            "meal_id": meal["id"],
        })
        mock.assert_called_once()

    assert r.status_code == 200
    assert r.json()["cached"] is False


# Verifies endpoint handles LLM unavailability gracefully
@pytest.mark.asyncio
async def test_analyze_meal_llm_unavailable(client):
    from services.llm import LLMUnavailableError

    async def mock_stream(*args, **kwargs):
        raise LLMUnavailableError("LLM down")
        yield  # make it an async generator

    with patch("routers.analyst.stream_response", side_effect=mock_stream):
        r = await client.post("/analyst/analyze", json={
            "meal_name": "Toast",
            "ingredients": ["ekmek", "peynir"],
        })

    assert r.status_code == 200
    data = r.json()
    assert len(data["analysis_text"]) > 0
    assert data["analysis_data"] is None


# Verifies endpoint validates request body
@pytest.mark.asyncio
async def test_analyze_meal_missing_fields(client):
    r = await client.post("/analyst/analyze", json={})
    assert r.status_code == 422


# Verifies empty ingredients list is handled
@pytest.mark.asyncio
async def test_analyze_meal_empty_ingredients(client):
    with patch("routers.analyst.stream_response", side_effect=_mock_stream_factory("Analiz tamamlandı.")):
        r = await client.post("/analyst/analyze", json={
            "meal_name": "Basit Kahvaltı",
            "ingredients": [],
        })

    assert r.status_code == 200
    assert "analysis_text" in r.json()


# Analysis without meal_id works but doesn't cache
@pytest.mark.asyncio
async def test_analyze_without_meal_id_no_cache(client):
    with patch("routers.analyst.stream_response", side_effect=_mock_stream_factory(MOCK_ANALYSIS)):
        r = await client.post("/analyst/analyze", json={
            "meal_name": "Ad hoc",
            "ingredients": ["yumurta"],
        })

    assert r.status_code == 200
    assert r.json()["cached"] is False
