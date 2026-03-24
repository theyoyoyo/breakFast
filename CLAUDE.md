# break FAST — Project Intelligence File

This file is the single source of truth for the break FAST project. Any AI assistant
working on this codebase should read this file in full before writing or modifying
anything. It captures product decisions, architectural choices, user context, and
feature specifications.

---

## What Is break FAST?

break FAST is an AI-powered breakfast planner designed for home/trusted circle use.
It is not a recipe website or a generic nutrition app. It is a system that knows
*each user* — their ingredients, their health context, their habits, and their
kitchen — and uses that knowledge to plan the richest, healthiest, most efficiently
prepared breakfast possible each morning with minimal decision-making effort.

Multiple users can use the same instance, each with their own profile, preferences,
health rules, and data — fully isolated. Authentication is simple (pin/name), managed
by an admin via CLI. Security is important as the app is accessible via Tailscale.

Users talk to it, tell it what's in the fridge, and the app handles the rest:
suggesting a full meal, producing a parallel cooking schedule optimized for the
available appliances, tracking what gets used, and getting smarter with every meal.

---

## Core Design Principles

**Reduce morning decision fatigue.** The user should never have to think hard in the
morning. The app suggests proactively; it doesn't interrogate. If it needs information
it doesn't have, it asks one question at a time, not a form.

**Health-aware by default, silently.** Each user can define their own health rules
(stored in DB, managed from Settings). The app factors these in automatically at the
suggestion layer — it never mentions the rules, never lectures, never explains why
it's favoring certain ingredients. It just makes good choices.

**Prep time is kitchen time, not idle time.** The app produces a cooking schedule that
treats the kitchen like a small factory floor — appliances are resources, food items
are jobs with durations and dependencies, and the goal is to minimize total wall-clock
time by running things in parallel wherever possible. This is formally a job-shop
scheduling problem.

**Local-first, free forever.** The primary AI brain runs on the user's own hardware
via Ollama. When the LLM is unreachable, a song lyric cycling fallback keeps the UI
responsive. The system is designed so that 100% of daily usage costs nothing.

**The system learns.** It starts with whatever the user tells it at onboarding and gets
smarter with every meal logged. Stated habits are treated as a warm prior, not hard
rules. Actual behavior over time gradually updates what the system recommends.

---

## Tech Stack

| Layer | Choice |
|---|---|
| Frontend | React PWA |
| Backend | Python / FastAPI |
| Local LLM | Ollama + Llama 3.1 8B |
| LLM Fallback | Song lyric cycling (when Ollama is unreachable) |
| Database | SQLite (local on third PC) |
| Voice | Web Speech API (browser-native) |
| Nutrition Data | Open Food Facts API + LLM estimation fallback |
| Remote Access | Tailscale |

---

## Architecture

```
[Android phone / Windows desktop — browser]
                  |
                  | HTTP / WebSocket
                  | (home WiFi or Tailscale tunnel)
                  v
        [FastAPI Backend — third PC]
          |                    |
          v                    v
   [Ollama + Llama 3.1]   [Song lyric fallback]
          |
          v
   [SQLite Database]
   - users, chat_sessions, chat_messages
   - ingredient_inventory, meal_history
   - user_preferences, user_habits, health_rules
   - user_profiles, user_supplements, supplement_daily_log
   - product_ratings
```

On home WiFi, the phone and desktop connect to the FastAPI backend directly over the
local network. Outside home WiFi, the connection goes through Tailscale — a private
WireGuard-based encrypted tunnel that gives the third PC a stable IP (100.x.x.x)
reachable from anywhere. No port forwarding or router configuration required. User
data traffic never passes through Tailscale's servers. The backend is started and
stopped manually by the user for now.

---

## User Profile

The owner is an advanced developer, comfortable with Python, FastAPI, and React. They
use Claude Code for development tasks and are on Android and Windows. They prefer to be
consulted before any architectural decision that goes beyond what is documented here.

### Health Context (Silent — Never Surface to User)

Health rules are per-user, stored in the `health_rules` DB table, and managed from
the Settings page. Users enter rules as free-text sentences (e.g., "Avoid refined
sugars", "Favor omega-3 sources like walnuts and flaxseed"). These rules are injected
into the system prompt at runtime — never referenced or explained to the user.

---

## Features

Phase 1 and Phase 2 are complete. Phase 3 is next.

### Phase 1 — MVP (COMPLETE)

- Chat interface with FastAPI + Ollama backend (WebSocket streaming)
- Ingredient input via natural language (parsed and stored)
- Meal suggestion engine (LLM with health rules in system prompt)
- Meal history logging (SQLite with timestamps)
- Multi-user authentication (PIN/name, admin CLI)
- Chat session persistence (messages survive refresh)

### Phase 2 — Core Experience (COMPLETE)

- Voice input and output (Web Speech API, browser-native)
- Meal blocks in chat (inline clickable blocks with checkboxes, prep time, editable overlay)
- Kitchen scheduler (greedy parallel prep planner — see spec below)
- Preference learning (thumbs up/down, product ratings 1-10)
- Preferences management (favorites, dislikes, habits, avoid list)
- "Kahvaltı Öner" button (suggest with comfort/explore/quick modes via long-press)
- "Karar Verdim" flow (confirm meal, rate ingredients, log to history)
- Analyst persona + meal nutrition analysis (score /100, macro breakdown)
- 3-step suggestion pipeline (draft → analyze → refine, max 2 rounds)
- User profiles (age, gender, height, weight, activity level)
- Supplements tracking (daily/sometimes frequency, today toggle)
- Health rules (free-text, priority levels: low/high/critical)
- Weekly summary (last 7 consecutive-day meals with cached nutrition)
- Song lyric fallback when Ollama is unreachable
- Settings page (profile, supplements, health rules, ratings, data management)

### Phase 3 — Smart Layer (NEXT)

**Habit import and onboarding.** A one-time onboarding conversation where the user
introduces their habits as a warm starting prior. Always editable afterward through
the preferences panel. The exact onboarding flow is to be decided when Phase 3 begins.

**Explore mode — "suggest me something new."** A first-class suggestion mode alongside
the default comfort mode. Steps deliberately outside the user's meal history while
respecting health context and available ingredients. The system builds a flavor and
technique graph from history and suggests adjacent-but-novel meals — not random
leaps. If the user frequently eats eggs and tomatoes and rates savory meals highly,
shakshuka is a good novel suggestion even if they've never made it.

**Ingredient expiry tracking.** Ingredients can have an optional expiry date. The
system checks for expired items since the last check and notifies the user via a
compact widget on the Ingredients page. Users confirm removal with a "Thrown" action.
No automatic depletion tracking — users manage their own inventory manually.

**Ingredient groups.** Users can organize ingredients into custom-named groups (e.g.,
"Dairy", "Spreads"). All items are always visible — no collapse. Group memory ensures
re-added ingredients return to their previous group automatically.

**Shopping assistant.** A new LLM persona — a professional shopping advisor that
cross-references inventory, meal history, preferences, favorites, habits, health
rules, supplements, and behavioral patterns. Over-suggests intentionally to expand
and enrich the user's breakfast experience. Shopping suggestions appear in a compact
widget on the Ingredients page; users pick what they want and send it to a persistent
shopping list. The shopping list has a "Bought" flow that adds checked items back as
ingredients.

**Weekly nutrition summary.** Extend the existing weekly summary view with deeper
nutritional analysis — what bases the user has covered this week and what's missing.
Factual, not preachy.

---

## Kitchen Scheduler Specification

### The Problem

When a meal has multiple components — a fried egg, air-fried potatoes, toast, yogurt
— there is an optimal order and parallelism to preparing them. A naive approach does
them sequentially and wastes time. The scheduler solves this by treating the kitchen
as a constrained parallel system.

### Formal Model

Each food item in a meal is a **job**. Each job has a list of **tasks** (peel, cut,
cook, plate, etc.). Each task has a **duration**, a **required resource**, and
optionally a list of **predecessor tasks** that must complete before it can start.
The goal is to minimize makespan — total time from first task to last — while never
assigning two tasks to the same resource simultaneously.

### Available Resources

- Air fryer (one)
- Toaster — Turkish-style, broader than a Western toaster (one)
- Stove (one active burner assumed unless specified)
- Hands — can only do one active manual task at a time, but can monitor a running
  appliance simultaneously

### Thermal Momentum

When the air fryer is used for one item and another item needs it shortly after, the
second item benefits from residual heat and may cook faster. The scheduler prefers
sequencing air fryer tasks back-to-back when possible and notes the thermal benefit
in the output.

### Output Format

```
0:00  — Start air fryer (potatoes). Preheat 2 min.
0:00  — While waiting: prepare egg (crack, season).
2:00  — Put potatoes in air fryer (12 min).
2:00  — Start stove on medium. Begin frying egg.
4:00  — Egg done. Plate it. Put bread in toaster.
5:30  — Toast done. Plate it. Prep yogurt + toppings.
14:00 — Potatoes done. Plate everything.
Total time: 14 minutes.
```

### Implementation Approach

Implement as a constraint-based scheduler in Python using a greedy earliest-start-time
algorithm with resource conflict checking. For 3–5 components this is fast and
produces good results without an integer programming solver. If complexity grows,
Google OR-Tools is the recommended upgrade path. Do not over-engineer for Phase 2 —
a greedy scheduler is the right starting point.

---

## Nutrition Data

The nutrition engine uses **Open Food Facts** as its primary source. The user is based
in Turkey, which makes US-centric databases like USDA FoodData Central a poor fit —
common Turkish ingredients (beyaz peynir, sucuk, simit, bulgur, mercimek, tahin,
ayran) either have no entry or an inaccurate proxy. Open Food Facts is a global
crowdsourced database with good Turkish coverage, is completely free, and requires no
API key.

For any ingredient not found or poorly covered, the system falls back to LLM
estimation and marks that value as approximate.

**Implementation note:** Every Open Food Facts API request must include a descriptive
`User-Agent` header — e.g. `"breakFAST/1.0 (personal project)"`. This is required
to prevent rate limiting. Set this in the nutrition service and do not omit it.

A small curated local dataset for the most frequently used Turkish ingredients can
be added in Phase 3 as an accuracy improvement.

---

## LLM System Prompts (Three Personas)

The system uses three distinct personas defined in `backend/services/suggestion.py`.
Prompts are written in English with "Always respond in Turkish" instruction — this
produces better results with Llama 3.1 8B than fully Turkish prompts. Turkish versions
are kept as comments for a future "Turkish brain / English brain" toggle.

| Persona | Job | Temperature | Defined in |
|---|---|---|---|
| Chat | Casual breakfast buddy | Ollama default | `build_chat_prompt` |
| Suggestion (favorites) | Creative meal designer | 0.6 | `build_suggestion_prompt` |
| Suggestion (explore) | Creative meal designer | 0.9 | `build_suggestion_prompt` |
| Analyst | Nutrition calculator + food expert | 0.3 | `build_analyst_prompt` |

### Chat Persona (`build_chat_prompt`)

Used for everyday conversation via the WebSocket chat endpoint.

- **Tone**: warm, friendly breakfast buddy — talks like a friend, not a chef
- **Context depth**: last 3 meals, current ingredients, preferences, habits
- **Health rules**: injected silently, never mentioned to user
- **Behavior**: steers non-breakfast topics back gently, confirms ingredient updates
  naturally, learns preferences through conversation
- **Output**: free-form Turkish text; appends a JSON block when suggesting a meal
  (parsed by frontend to render MealBlock and log the meal)

### Suggestion Persona (`build_suggestion_prompt`)

Used when the "Kahvaltı Öner" button is pressed. Supports three modes:
comfort (default short press), explore, and quick (long-press selection).

- **Tone**: professional dietitian who explains like an experienced chef
- **Context depth**: last 10 meals, full ingredient inventory, user profile,
  supplement intake, preferences, habits, behavioral patterns
- **Physical profile**: uses age/gender/height/weight/activity to calculate daily
  caloric needs (Harris-Benedict/Mifflin-St Jeor), targets ~30% for breakfast
- **Supplements**: daily ones assumed taken (deprioritize those nutrients),
  "sometimes" ones check today's toggle status, fills gaps through food
- **Nutrition analysis**: mandatory for every suggestion — calories, macros, fiber,
  key vitamins/minerals, omega-3 sources, weekly balance review
- **Avoid list**: hard ban — never suggest avoided ingredients, suggest alternatives
- **Seasonality**: prefer seasonal produce (hint, not hard constraint)
- **Advance prep tips**: if overnight soak or pre-chop helps, note it at recipe start
- **Output**: structured Turkish response with nutrition detail + JSON block including
  `nutrition_detail` object and `advance_prep_tip` field

### Analyst Persona (`build_analyst_prompt`)

Used by the analyst endpoint and the 3-step suggestion pipeline.

- **Tone**: precise, data-driven nutrition expert
- **Role**: evaluates meals for nutritional completeness, scores them, identifies gaps
- **Food knowledge**: shares `backend/services/knowledge.py` module with Suggestion
- **Output**: structured analysis with score /100, macro/micro breakdown, suggestions

### 3-Step Suggestion Pipeline

Defined in `backend/services/pipeline.py`. When a suggestion is requested:

1. **Draft** — Suggestion persona generates a meal proposal
2. **Analyze** — Analyst persona evaluates the draft (nutrition, balance, health rules)
3. **Refine** — Suggestion persona revises based on analyst feedback (max 2 rounds)

Progress updates are streamed to the frontend via WebSocket `{type: 'progress'}` messages.

### Shared Context Formatters

All three personas share formatting functions for ingredients, history, preferences,
habits, health rules, behavioral patterns, user profile, and supplements. These
are injected into template placeholders at runtime. Food knowledge data lives in
`backend/services/knowledge.py` and is shared by Suggestion and Analyst.

---

## Project File Structure

```
breakFAST/
├── CLAUDE.md                        ← this file, always read first
├── README.md                        ← setup instructions for the third PC
├── .env.example                     ← environment variable template
├── .gitattributes                   ← line ending normalization (LF in repo)
├── start.bat                        ← Windows convenience launcher
│
├── backend/
│   ├── main.py                      ← FastAPI app entry point, lifespan init_db
│   ├── requirements.txt
│   ├── requirements-dev.txt         ← test dependencies (pytest, pytest-asyncio)
│   ├── config.py                    ← LLM endpoints, model names, env config
│   ├── database.py                  ← SQLite connection, schema, indices
│   ├── auth.py                      ← JWT auth (require_user dependency)
│   ├── manage.py                    ← admin CLI (add/remove/list users)
│   ├── utils.py                     ← shared utilities (JSON block extraction)
│   ├── db_helpers.py                ← reusable DB query helpers
│   │
│   ├── routers/
│   │   ├── analyst.py             ← /analyst/analyze meal analysis endpoint
│   │   ├── auth.py                  ← /auth/login endpoint
│   │   ├── chat.py                  ← /chat WebSocket endpoint
│   │   ├── favorites.py            ← /favorites CRUD endpoints
│   │   ├── health_rules.py        ← /health-rules CRUD with priority
│   │   ├── ingredients.py           ← /ingredients CRUD endpoints
│   │   ├── meals.py                 ← /meals history + /meals/weekly
│   │   ├── preferences.py          ← /preferences + /preferences/habits
│   │   ├── profile.py             ← /profile + /profile/supplements CRUD
│   │   ├── ratings.py              ← /ratings CRUD endpoints (1-10 scale)
│   │   └── sessions.py            ← /sessions chat session management
│   │
│   ├── services/
│   │   ├── context.py               ← shared context loaders for LLM prompts
│   │   ├── llm.py                   ← Ollama streaming + FallbackLyricCycler
│   │   ├── scheduler.py             ← kitchen job-shop scheduler
│   │   ├── suggestion.py            ← three persona prompts + prompt assembly
│   │   ├── knowledge.py            ← shared food knowledge module
│   │   ├── pipeline.py             ← 3-step suggestion pipeline
│   │   ├── insights.py             ← behavioral pattern extraction
│   │   └── nutrition.py             ← Open Food Facts integration
│   │
│   ├── models/
│   │   ├── ingredient.py            ← Pydantic models for ingredients
│   │   ├── meal.py                  ← Pydantic models for meals
│   │   ├── user.py                 ← Pydantic models for auth/users
│   │   └── preferences.py          ← Pydantic models for user preferences
│   │
│   └── tests/
│       ├── conftest.py              ← shared fixtures (test DB, async client)
│       ├── test_utils.py            ← extract_json_block unit tests
│       ├── api/
│       │   ├── test_auth.py         ← auth endpoint tests
│       │   ├── test_ingredients.py  ← ingredient endpoint tests
│       │   ├── test_meals.py        ← meal endpoint tests
│       │   ├── test_weekly.py       ← weekly meals endpoint tests
│       │   ├── test_preferences.py  ← preference endpoint tests
│       │   ├── test_ratings.py      ← rating endpoint tests
│       │   ├── test_profile.py      ← profile + supplement tests
│       │   ├── test_health_rules.py ← health rules endpoint tests
│       │   ├── test_analyst.py      ← analyst endpoint tests
│       │   ├── test_websocket.py    ← WebSocket chat tests
│       │   └── test_sessions.py     ← session management tests
│       └── services/
│           ├── test_prompts.py      ← prompt builder unit tests
│           ├── test_scheduler.py    ← scheduler logic unit tests
│           ├── test_knowledge.py    ← food knowledge module tests
│           ├── test_pipeline.py     ← suggestion pipeline tests
│           ├── test_insights.py     ← behavioral insights tests
│           ├── test_llm_fallback.py ← lyric cycler fallback tests
│           └── test_cleanup.py      ← cleanup utility tests
│
└── frontend/
    ├── public/
    │   └── manifest.json            ← PWA manifest
    ├── src/
    │   ├── main.jsx                 ← React entry point
    │   ├── App.jsx                  ← tab navigation (Chat, Ingredients, Preferences, Settings)
    │   ├── App.styles.js            ← App layout styles
    │   ├── test-setup.js            ← vitest setup (jest-dom matchers)
    │   ├── styles/
    │   │   └── common.js            ← shared style definitions (panelContainer, input, etc.)
    │   ├── components/
    │   │   ├── ChatInterface.jsx    ← main chat UI + supplement toggle bar
    │   │   ├── MealBlock.jsx        ← inline meal suggestion block in chat
    │   │   ├── DecidePanel.jsx      ← "Today I ate..." confirm + rate flow
    │   │   ├── SuggestButton.jsx    ← suggest button + long-press mode panel
    │   │   ├── WeeklySummary.jsx    ← weekly meals summary view
    │   │   ├── IngredientPanel.jsx  ← inventory viewer/editor
    │   │   ├── PreferencesPanel.jsx ← favorites, dislikes, habits, avoid list
    │   │   ├── SettingsPanel.jsx    ← profile, supplements, ratings, health rules
    │   │   ├── LoginScreen.jsx      ← PIN auth screen
    │   │   └── *.styles.js          ← per-component style files
    │   ├── services/
    │   │   ├── api.js               ← backend API calls (REST + WebSocket)
    │   │   └── api.test.js          ← API service tests
    │   └── hooks/
    │       └── useVoice.js          ← Web Speech API hook
    └── package.json
```

---

## Glossary

**Makespan** — total wall-clock time from start of the first task to end of the last
task in a cooking schedule. The scheduler minimizes this.

**Job-shop scheduling** — a class of optimization problems where a set of jobs must
be processed on a set of machines in a specific order, with no two jobs using the
same machine simultaneously. The formal model for the kitchen scheduler.

**Warm prior** — a starting assumption based on stated habits that is gradually
updated by observed behavior. The system starts believing what the user says, then
adjusts based on what the user actually does.

**Comfort mode** — the default suggestion mode, optimizing for meals the user is
likely to enjoy based on history and preferences.

**Explore mode** — an alternative suggestion mode that finds novel meals adjacent to
the user's taste profile rather than defaulting to familiar choices.
