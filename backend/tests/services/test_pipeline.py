"""
Tests for the 3-step suggestion pipeline (draft → analyze → refine).
"""

import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest

from services.suggestion import build_pipeline_analyst_prompt
from services.pipeline import run_suggestion_pipeline


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_CONTEXT = {
    "ingredients": [{"name": "eggs", "quantity": "6", "unit": "pcs"}],
    "history": [{"meal_name": "Menemen", "ingredients": '["eggs", "tomato"]'}],
    "preferences": {"favorite": "eggs"},
    "stated_habits": ["early breakfast"],
    "inferred_habits": None,
    "health_rules": [{"rule_text": "Favor omega-3", "priority": "high"}],
    "user_profile": {"age": 30, "gender": "erkek", "height_cm": 180, "weight_kg": 75, "activity_level": "orta"},
    "supplements": [{"name": "Vitamin D", "frequency": "daily", "contents": "1000IU D3"}],
    "avoid_list": ["shellfish"],
}


# ---------------------------------------------------------------------------
# Pipeline analyst prompt builder
# ---------------------------------------------------------------------------

class TestPipelineAnalystPrompt:
    # Prompt contains the internal reviewer identity
    def test_contains_reviewer_identity(self):
        prompt = build_pipeline_analyst_prompt(
            recent_meal_history=SAMPLE_CONTEXT["history"],
        )
        assert "harsh" in prompt.lower() or "internal reviewer" in prompt.lower()
        assert "Always respond in English." in prompt

    def test_respects_turkish_language_setting(self):
        prompt = build_pipeline_analyst_prompt(
            recent_meal_history=SAMPLE_CONTEXT["history"], language="tr",
        )
        assert "Always respond in Turkish." in prompt

    # Prompt injects user profile data
    def test_injects_user_profile(self):
        prompt = build_pipeline_analyst_prompt(
            recent_meal_history=SAMPLE_CONTEXT["history"],
            user_profile=SAMPLE_CONTEXT["user_profile"],
        )
        assert "180" in prompt
        assert "75" in prompt

    # Prompt injects supplements
    def test_injects_supplements(self):
        prompt = build_pipeline_analyst_prompt(
            recent_meal_history=SAMPLE_CONTEXT["history"],
            supplements=SAMPLE_CONTEXT["supplements"],
        )
        assert "Vitamin D" in prompt

    # Prompt injects health rules
    def test_injects_health_rules(self):
        prompt = build_pipeline_analyst_prompt(
            recent_meal_history=SAMPLE_CONTEXT["history"],
            health_rules=SAMPLE_CONTEXT["health_rules"],
        )
        assert "omega-3" in prompt.lower()

    # Prompt injects meal history
    def test_injects_history(self):
        prompt = build_pipeline_analyst_prompt(
            recent_meal_history=SAMPLE_CONTEXT["history"],
        )
        assert "Menemen" in prompt

    # Prompt requests JSON feedback list output
    def test_requests_json_feedback_format(self):
        prompt = build_pipeline_analyst_prompt(
            recent_meal_history=[],
        )
        assert '"feedback"' in prompt

    # Prompt covers all review areas
    def test_covers_review_areas(self):
        prompt = build_pipeline_analyst_prompt(
            recent_meal_history=[],
        )
        for keyword in ["MACRONUTRIENT", "MICRONUTRIENT", "INGREDIENT QUALITY", "VARIETY", "SUPPLEMENT", "PRACTICAL"]:
            assert keyword in prompt.upper(), f"Missing review area: {keyword}"


# ---------------------------------------------------------------------------
# Pipeline orchestrator
# ---------------------------------------------------------------------------

# Helper to make a fake stream_response that yields pre-defined chunks
def _make_fake_stream(responses):
    """Return an async generator factory that yields from a list of responses in order."""
    call_count = {"n": 0}

    async def fake_stream(system_prompt, history, message, temperature=None):
        idx = call_count["n"]
        call_count["n"] += 1
        text = responses[idx] if idx < len(responses) else ""
        for char in text:
            yield char

    return fake_stream


class TestPipelineOrchestrator:
    # Pipeline yields progress events in correct order
    @pytest.mark.asyncio
    async def test_yields_progress_events_in_order(self):
        draft = "Draft meal text"
        analyst_feedback = '```json\n{"feedback": ["Add more protein"]}\n```'
        final = "Final refined meal"

        fake_stream = _make_fake_stream([draft, analyst_feedback, final])

        with patch("services.pipeline.stream_response", fake_stream):
            events = []
            async for event in run_suggestion_pipeline(
                context=SAMPLE_CONTEXT,
                user_message="Bana kahvaltı öner",
            ):
                events.append(event)

        # First three unique types should be progress events in order
        progress_events = [e for e in events if e["type"] == "progress"]
        assert len(progress_events) == 3
        assert progress_events[0]["step"] == "drafting"
        assert progress_events[1]["step"] == "analyzing"
        assert progress_events[2]["step"] == "finalizing"

    # Pipeline yields token events for the final refined response
    @pytest.mark.asyncio
    async def test_yields_final_tokens(self):
        draft = "Draft text"
        analyst_feedback = '```json\n{"feedback": ["Fix protein"]}\n```'
        final = "Hello"

        fake_stream = _make_fake_stream([draft, analyst_feedback, final])

        with patch("services.pipeline.stream_response", fake_stream):
            token_events = []
            async for event in run_suggestion_pipeline(
                context=SAMPLE_CONTEXT,
                user_message="Bana kahvaltı öner",
            ):
                if event["type"] == "token":
                    token_events.append(event["content"])

        # Each character of "Hello" should be a token event
        assert "".join(token_events) == "Hello"

    # Pipeline yields a done event with the full final text
    @pytest.mark.asyncio
    async def test_yields_done_event(self):
        draft = "Draft"
        analyst = '```json\n{"feedback": ["OK"]}\n```'
        final = "Final meal"

        fake_stream = _make_fake_stream([draft, analyst, final])

        with patch("services.pipeline.stream_response", fake_stream):
            done_events = []
            async for event in run_suggestion_pipeline(
                context=SAMPLE_CONTEXT,
                user_message="Bana kahvaltı öner",
            ):
                if event["type"] == "done":
                    done_events.append(event)

        assert len(done_events) == 1
        assert done_events[0]["content"] == "Final meal"

    # Pipeline passes analyst feedback to the refinement step
    @pytest.mark.asyncio
    async def test_passes_feedback_to_refinement(self):
        draft = "Draft meal with eggs"
        analyst = '```json\n{"feedback": ["Protein yetersiz, en az 20g olmalı", "Omega-3 kaynağı yok"]}\n```'
        final = "Refined meal"

        captured_messages = []

        async def capturing_stream(system_prompt, history, message, temperature=None):
            captured_messages.append(message)
            idx = len(captured_messages) - 1
            texts = [draft, analyst, final]
            text = texts[idx] if idx < len(texts) else ""
            for char in text:
                yield char

        with patch("services.pipeline.stream_response", capturing_stream):
            async for _ in run_suggestion_pipeline(
                context=SAMPLE_CONTEXT,
                user_message="Bana kahvaltı öner",
            ):
                pass

        # Third call (refinement) should contain analyst feedback
        refinement_msg = captured_messages[2]
        assert "Protein yetersiz" in refinement_msg
        assert "Omega-3 kaynağı yok" in refinement_msg
        assert "Draft meal with eggs" in refinement_msg

    # Pipeline falls back to raw text when analyst doesn't produce valid JSON
    @pytest.mark.asyncio
    async def test_fallback_when_analyst_no_json(self):
        draft = "Draft"
        analyst = "Protein is too low. Add walnuts for omega-3."
        final = "Refined"

        captured_messages = []

        async def capturing_stream(system_prompt, history, message, temperature=None):
            captured_messages.append(message)
            idx = len(captured_messages) - 1
            texts = [draft, analyst, final]
            text = texts[idx] if idx < len(texts) else ""
            for char in text:
                yield char

        with patch("services.pipeline.stream_response", capturing_stream):
            async for _ in run_suggestion_pipeline(
                context=SAMPLE_CONTEXT,
                user_message="Bana kahvaltı öner",
            ):
                pass

        # Refinement should still contain the raw analyst text
        refinement_msg = captured_messages[2]
        assert "Protein is too low" in refinement_msg
        assert "Add walnuts" in refinement_msg

    # Pipeline passes temperature and mode through to suggestion calls
    @pytest.mark.asyncio
    async def test_passes_temperature_and_mode(self):
        captured_temps = []
        captured_prompts = []

        async def temp_tracking_stream(system_prompt, history, message, temperature=None):
            captured_temps.append(temperature)
            captured_prompts.append(system_prompt)
            for char in "ok":
                yield char

        with patch("services.pipeline.stream_response", temp_tracking_stream):
            async for _ in run_suggestion_pipeline(
                context=SAMPLE_CONTEXT,
                user_message="Öner",
                mode="explore",
                temperature=0.9,
            ):
                pass

        # Call 1 (draft): suggestion temp 0.9
        assert captured_temps[0] == 0.9
        # Call 2 (analyst): always 0.3
        assert captured_temps[1] == 0.3
        # Call 3 (refine): suggestion temp 0.9
        assert captured_temps[2] == 0.9
        # Suggestion prompts (1st and 3rd) should contain EXPLORE mode
        assert "EXPLORE" in captured_prompts[0]
        assert "EXPLORE" in captured_prompts[2]

    # Pipeline propagates LLMUnavailableError from draft step
    @pytest.mark.asyncio
    async def test_propagates_llm_error(self):
        from services.llm import LLMUnavailableError

        async def failing_stream(system_prompt, history, message, temperature=None):
            raise LLMUnavailableError("Ollama down")
            yield  # make it a generator

        with patch("services.pipeline.stream_response", failing_stream):
            with pytest.raises(LLMUnavailableError):
                async for _ in run_suggestion_pipeline(
                    context=SAMPLE_CONTEXT,
                    user_message="Öner",
                ):
                    pass
