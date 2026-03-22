"""
Tests for the /analyst endpoint — nutrition analysis REST API.
Mocks the LLM to test endpoint logic without requiring Ollama.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest
from unittest.mock import AsyncMock, patch


# Verifies endpoint returns 200 with mocked LLM response
@pytest.mark.asyncio
async def test_analyze_meal_success(client):
    mock_response = (
        "Bu kahvaltı protein açısından zengin.\n\n"
        "```json\n"
        '{"narrative": "Test narrative", "daily_coverage": [], "macros": {"calories_kcal": 400}, "micros": []}\n'
        "```"
    )

    async def mock_stream(*args, **kwargs):
        for chunk in mock_response.split():
            yield chunk + " "

    with patch("routers.analyst.stream_response", side_effect=mock_stream):
        r = await client.post("/analyst/analyze", json={
            "meal_name": "Menemen",
            "ingredients": ["yumurta", "domates", "biber"],
        })

    assert r.status_code == 200
    data = r.json()
    assert "analysis_text" in data
    assert data["analysis_data"] is not None or data["analysis_text"] != ""


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
    assert "kullanılamıyor" in data["analysis_text"]
    assert data["analysis_data"] is None


# Verifies endpoint validates request body
@pytest.mark.asyncio
async def test_analyze_meal_missing_fields(client):
    r = await client.post("/analyst/analyze", json={})
    assert r.status_code == 422


# Verifies empty ingredients list is handled
@pytest.mark.asyncio
async def test_analyze_meal_empty_ingredients(client):
    mock_response = "Analiz tamamlandı."

    async def mock_stream(*args, **kwargs):
        yield mock_response

    with patch("routers.analyst.stream_response", side_effect=mock_stream):
        r = await client.post("/analyst/analyze", json={
            "meal_name": "Basit Kahvaltı",
            "ingredients": [],
        })

    assert r.status_code == 200
    data = r.json()
    assert "analysis_text" in data
