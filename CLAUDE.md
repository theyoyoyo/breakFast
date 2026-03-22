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
via Ollama. The Claude API is a fallback only — for when the local server is down or
for tasks that genuinely require stronger reasoning. The system is designed so that
95% of daily usage costs nothing.

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
| LLM Fallback | Anthropic Claude API (commented out, to be re-enabled later) |
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
   [Ollama + Llama 3.1]   [Claude API fallback]
          |
          v
   [SQLite Database]
   - ingredient_inventory
   - meal_history
   - user_preferences
   - user_habits
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

Features are in implementation priority order. Nothing in Phase 2 or later should be
built before Phase 1 is solid and tested.

### Phase 1 — MVP

**Chat interface with FastAPI + Ollama backend.** Text-based conversation, streaming
responses via WebSocket. The user describes what they have and what they want. The app
responds with a full meal suggestion including ingredients, steps, rough prep time,
and a one-line nutrition note.

**Ingredient input via natural language.** The user says things like "I have eggs,
some leftover rice, a tomato, and Greek yogurt" and the system parses and stores this.
"I used the eggs" or "I bought oats and kefir" update the inventory accordingly.

**Meal suggestion engine (basic).** Using the ingredient inventory and health profile,
suggest a complete breakfast. Suggestions come from the LLM with health rules baked
into the system prompt.

**Meal history logging.** Every accepted/prepared meal is saved to SQLite with a
timestamp. This is the data foundation everything in Phase 2 builds on.

### Phase 2 — Core Experience

**Voice input and output.** Hands-free use in the kitchen via Web Speech API. Voice
is a frontend layer only — speech to text before sending, text to speech after
receiving. The backend does not change.

**Visual recipe card UI.** A structured recipe card renders alongside the chat showing
the meal name, ingredients, timed steps, and nutrition note.

**Kitchen scheduler (parallel prep planner).** Given a multi-component meal, the
system produces a step-by-step cooking schedule that minimizes total wall-clock time
by parallelizing tasks across appliances. Full specification in the Kitchen Scheduler
section below.

**Preference learning.** Thumbs up/down feedback and repeat meal requests update the
preference profile in SQLite and influence future suggestions.

**Preferences management.** A dedicated panel where the user can view and edit
favorites, dislikes, and habits — editable both through chat ("add avocado to my
favorites") and through the UI directly.

### Phase 3 — Smart Layer

**Habit import and onboarding.** A one-time onboarding conversation where the user
introduces their habits as a warm starting prior. Always editable afterward through
the preferences panel. The exact onboarding flow is to be decided when Phase 3 begins.

**Explore mode — "suggest me something new."** A first-class suggestion mode alongside
the default comfort mode. Steps deliberately outside the user's meal history while
respecting health context and available ingredients. The system builds a flavor and
technique graph from history and suggests adjacent-but-novel meals — not random
leaps. If the user frequently eats eggs and tomatoes and rates savory meals highly,
shakshuka is a good novel suggestion even if they've never made it.

**Ingredient depletion inference.** The system tracks which ingredients go into logged
meals and estimates remaining quantities automatically. Manual correction only needed
when something is off. Soft inference layer on top of the hard inventory.

**Smart shopping suggestions.** Cross-references inventory, meal history, health
profile, and nutrition data. Not just "you're out of eggs" but "you haven't had a
good omega-3 source in several days and you're low on walnuts — consider picking
those up."

**Weekly nutrition summary.** A simple view of what nutritional bases the user has
covered this week and what's missing. Factual, not preachy.

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

## LLM System Prompts (Dual Persona)

The system uses two distinct personas, both defined in `backend/services/suggestion.py`.
Prompts are written in English with "Always respond in Turkish" instruction — this
produces better results with Llama 3.1 8B than fully Turkish prompts. Turkish versions
are kept as comments for a future "Turkish brain / English brain" toggle.

### Chat Persona (`build_chat_prompt`)

Used for everyday conversation via the WebSocket chat endpoint.

- **Tone**: warm, friendly breakfast buddy — talks like a friend, not a chef
- **Context depth**: last 3 meals, current ingredients, preferences, habits
- **Health rules**: injected silently, never mentioned to user
- **Behavior**: steers non-breakfast topics back gently, confirms ingredient updates
  naturally, learns preferences through conversation
- **Output**: free-form Turkish text; appends a JSON block when suggesting a meal
  (parsed by frontend to render RecipeCard and log the meal)

### Suggestion Persona (`build_suggestion_prompt`)

Used when the "Kahvaltı Öner" button is pressed (Issue #16, not yet implemented).

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

### Shared Context Formatters

Both personas share formatting functions for ingredients, history, preferences,
habits, health rules, behavioral patterns, user profile, and supplements. These
are injected into template placeholders at runtime.

---

## Project File Structure

```
breakFAST/
├── CLAUDE.md                        ← this file, always read first
├── README.md                        ← setup instructions for the third PC
├── .env.example                     ← environment variable template
│
├── backend/
│   ├── main.py                      ← FastAPI app entry point
│   ├── requirements.txt
│   ├── requirements-dev.txt         ← test dependencies (pytest, pytest-asyncio)
│   ├── config.py                    ← LLM endpoints, model names, env config
│   ├── database.py                  ← SQLite connection and schema setup
│   ├── utils.py                     ← shared utilities (JSON block extraction)
│   │
│   ├── routers/
│   │   ├── chat.py                  ← /chat WebSocket endpoint
│   │   ├── ingredients.py           ← /ingredients CRUD endpoints
│   │   ├── meals.py                 ← /meals history endpoints
│   │   ├── preferences.py          ← /preferences read/write endpoints
│   │   ├── ratings.py              ← /ratings CRUD endpoints (1-10 scale)
│   │   └── profile.py             ← /profile + /profile/supplements CRUD
│   │
│   ├── services/
│   │   ├── llm.py                   ← Ollama + Claude API abstraction layer
│   │   ├── scheduler.py             ← kitchen job-shop scheduler
│   │   ├── suggestion.py            ← dual persona prompts + prompt assembly
│   │   ├── nutrition.py             ← Open Food Facts integration
│   │   └── depletion.py            ← ingredient depletion inference (Phase 3)
│   │
│   ├── models/
│   │   ├── ingredient.py            ← Pydantic models for ingredients
│   │   ├── meal.py                  ← Pydantic models for meals
│   │   └── preferences.py          ← Pydantic models for user preferences
│   │
│   └── tests/
│       ├── conftest.py              ← shared fixtures (test DB, async client)
│       ├── api/
│       │   ├── test_ingredients.py  ← ingredient endpoint integration tests
│       │   ├── test_meals.py        ← meal endpoint integration tests
│       │   ├── test_preferences.py  ← preference endpoint integration tests
│       │   ├── test_ratings.py      ← rating endpoint integration tests
│       │   ├── test_profile.py      ← profile + supplement endpoint tests
│       │   ├── test_websocket.py    ← WebSocket chat tests
│       │   └── test_sessions.py     ← session management tests
│       └── services/
│           ├── test_utils.py        ← extract_json_block unit tests
│           ├── test_scheduler.py    ← scheduler logic unit tests
│           └── test_prompts.py      ← prompt builder unit tests (43 tests)
│
└── frontend/
    ├── public/
    │   └── manifest.json            ← PWA manifest
    ├── src/
    │   ├── App.jsx                  ← tab navigation (Chat, Ingredients, Preferences, Settings)
    │   ├── App.styles.js            ← App layout styles
    │   ├── test-setup.js            ← vitest setup (jest-dom matchers)
    │   ├── styles/
    │   │   └── common.js            ← shared style definitions (panelContainer, input, etc.)
    │   ├── components/
    │   │   ├── ChatInterface.jsx    ← main chat UI + supplement toggle bar
    │   │   ├── RecipeCard.jsx       ← visual meal card + thumbs up/down
    │   │   ├── ScheduleTimeline.jsx ← cooking schedule display
    │   │   ├── IngredientPanel.jsx  ← inventory viewer/editor
    │   │   ├── PreferencesPanel.jsx ← favorites, dislikes, habits
    │   │   ├── SettingsPanel.jsx    ← profile, supplements, ratings
    │   │   ├── LoginScreen.jsx      ← PIN auth screen
    │   │   └── *.styles.js          ← per-component style files
    │   ├── services/
    │   │   └── api.js               ← backend API calls
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
