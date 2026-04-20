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
   - ingredient_inventory, ingredient_group_memory
   - favorite_ingredients, shopping_list
   - meal_history, product_ratings
   - user_preferences, user_habits, health_rules
   - user_profiles, user_supplements, supplement_daily_log
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

Phase 1 and Phase 2 are complete. Phase 3 is in progress.

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

### Phase 3 — Smart Layer (IN PROGRESS)

#### Completed

**Ingredient expiry tracking.** Ingredients have an optional expiry date. The system
checks for expired items and notifies the user via a compact widget on the Fridge tab.
Users can take action per item: "Thrown" (delete), "Keep" (acknowledge but retain), or
"Shopping" (delete and add to shopping list). Kept items show a `(kept)` indicator
next to their bold expiry date in the main list, and the expiry panel header shows
`· N kept` count. No automatic depletion tracking — users manage inventory manually.

**Ingredient groups.** 10 fixed Turkish groups with emojis: 🐄 Hayvansal, 🥬 Sebze
Meyve, 🍞 Ekmekler, 🍯 Tatlılar, 🫒 Kahvaltılık, 🥜 Kuruyemişler, 🌱 Bitkisel,
☕ İçecekler, 🧂 Baharatlar, 🍽️ Diğer. No custom group creation or deletion. Groups
are collapsible with collapse state persisted in localStorage. Empty groups are hidden.
Deterministic background colors hashed from group name. Group dropdown in add/edit
panels. Group memory via `ingredient_group_memory` table ensures re-added ingredients
return to their previous group automatically. New ingredients default to 🍽️ Diğer.
Group names are Turkish and fed to LLM personas for context. The group list is defined
in `backend/models/ingredient.py` (INGREDIENT_GROUPS) and mirrored in
`IngredientPanel.jsx`. The number of groups can be adjusted in the future by editing
these two locations.

**Favorite ingredients.** A "staples" list independent from the ingredient inventory —
favorites survive when items are deleted from the fridge. Stored in the
`favorite_ingredients` DB table with per-user isolation. Heart toggle ❤️ on each
ingredient row (optimistic UI with revert on failure). ❤️ button in Fridge header
opens an overlay panel listing all favorites. Each favorite can be individually added
to the shopping list, or bulk-added via "Add All" button. Panel cross-references
the shopping list to show "In list" / "Added" status per item. Backend CRUD at
`/favorite-ingredients/` (GET list, POST add 201/409, DELETE by name 200/404).

**Shopping list.** Persistent shopping list with CRUD endpoints. "Bought" flow adds
checked items back as ingredients. Accessible from Fridge tab header via 🛒 button.

**Delete confirm redesign.** Clicking the trash icon on an ingredient no longer
instantly deletes. Instead, two inline buttons appear below the trash: 🗑️ (confirm
delete) and 🛒 (delete + add to shopping list). Clicking anywhere else on the page
dismisses without deleting — this serves as the cancel/confirm mechanism.

**Fridge tab rename.** The Ingredients tab was renamed to "Fridge" (header text and
tab label in App.jsx).

**Kitchen appliances settings.** Configurable per-user appliance list in Settings.
9 fixed appliances: Ocak, Fırın, Airfryer, Ekmek Kızartma Makinesi, Mikrodalga,
Blender, Tost Makinesi, Su Isıtıcı, French Press. Only Ocak (stove) is enabled by
default — users enable the rest from a grid of toggle tiles. Stored in
`user_kitchen_appliances` DB table (per-user, appliance_key + enabled). Auto-populated
on first access. Backend CRUD at `/kitchen/` (GET list, PUT toggle). Enabled appliances
are injected into all LLM persona prompts (chat, suggestion, shopping, scheduler) as
a dynamic context line — the LLM uses its own knowledge about each appliance's
capabilities (batching, multi-burner, etc.) without per-appliance hardcoded notes.
Appliance list defined in `backend/models/kitchen.py` (KITCHEN_APPLIANCES). Frontend
component: `KitchenSettings.jsx`, accessible from Settings → Kitchen sub-page.

**Multi-item menu format.** LLM now returns a full breakfast menu instead of a single
dish. The JSON schema uses `menu_name`, `menu[]` where each item is either a complex
dish (no top-level `amount`, has `ingredients[]` sub-array) or a simple item (has
`amount` + `unit`, empty `ingredients[]`). DB: `menu_items TEXT` column added to
`meal_history`, `suggested_meals`, `favorite_meals` via ALTER TABLE migrations.
`MealLog` and `Meal` models updated. `_save_suggestion` stores full menu and derives
flat ingredients for backward compat. Old flat-format meals continue to work via
`normalizeMeal()` in the frontend. `isSimpleItem(item)` = `item.amount != null`.

**Suggestion text simplified.** The suggestion persona no longer outputs prep steps,
cooking timelines, nutrition tables, vitamin notes, or supplement context in the
response text. Those details belong in the 📊 Analyze and 📋 Prep Timeline buttons.
Tips in the text are taste/texture only (e.g. "yulafı sütte bekletirsen kremsi olur").

**Shared MealEditor.** A single `MealEditor` component handles all meal editing across
chat, favorites, meal history, and "Today I ate". Complex dishes show a
"▶ Ingredients" expand button revealing sub-ingredients inline. Menu mode has separate
"+ Item" and "+ Dish" add buttons. Unit field is a subtle dropdown (blends with text)
with smart keyword defaults (`zeytinyağı → yemek kaşığı`, `yumurta → adet`, etc.) and
localStorage memory per ingredient name — recalled on next add. Utilities in
`frontend/src/utils/ingredients.js`: `UNITS`, `getSmartUnit`, `resolveUnit`,
`rememberUnit`, `recallUnit`.

**Meal editing patterns standardised.** Favorites panel and meal history in Settings
both use an overlay edit pattern: a ✏️ button opens a full-screen `MealEditor` overlay
(backdrop click to dismiss). No more inline expand/collapse dropdowns for editing.

**"Today I ate" panel.** Uses `MealEditor` with `menuMode=true`. Flat-ingredient meals
from old format are auto-converted to simple menu items on open. Save logs directly;
Confirm goes to the star-rating phase first. `extraActions` prop on MealEditor accepts
a function `(buildCurrentMeal) => ReactNode` so the Confirm button captures live editor
state rather than the stale meal prop.

#### Remaining

**Habit import and onboarding.** A one-time onboarding conversation where the user
introduces their habits as a warm starting prior. Always editable afterward through
the preferences panel. The exact onboarding flow is to be decided.

**Explore mode — "suggest me something new."** A first-class suggestion mode alongside
the default comfort mode. Steps deliberately outside the user's meal history while
respecting health context and available ingredients. The system builds a flavor and
technique graph from history and suggests adjacent-but-novel meals — not random
leaps. If the user frequently eats eggs and tomatoes and rates savory meals highly,
shakshuka is a good novel suggestion even if they've never made it.

**Shopping assistant (LLM persona).** A new LLM persona — a professional shopping
advisor that cross-references inventory, meal history, preferences, favorites, habits,
health rules, supplements, and behavioral patterns. Over-suggests intentionally to
expand and enrich the user's breakfast experience. Shopping suggestions appear in a
compact widget on the Fridge tab; users pick what they want and send it to the
persistent shopping list.

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

- Air fryer (one) — can hold multiple similar items simultaneously (e.g., onion
  rings + potato fries + spring rolls + frozen pastries in one batch)
- Toaster — Turkish-style, broader than a Western toaster (one)
- Stove — multiple burners can be used simultaneously
- Hands — can only do one active manual task at a time, but can monitor a running
  appliance simultaneously

**Note:** The available resources listed above are the legacy hardcoded defaults.
The Kitchen Settings feature (Phase 3) lets users configure which appliances they
own — see `docs/kitchen_task.md`. All LLM personas and the scheduler now use the
user's configured appliances instead of this hardcoded list.

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

## LLM System Prompts (Six Personas)

The system uses six distinct personas defined in `backend/services/personas/`.
Prompts are written in English with "Always respond in Turkish" instruction. A
Settings toggle for English responses is planned (English will be the default when
implemented — the Turkish path will remain in place).

| Persona | Job | Temperature | File |
|---|---|---|---|
| Chat | Casual breakfast buddy | Ollama default | `personas/chat.py` |
| Suggestion (comfort) | Creative meal designer | 0.6 | `personas/dietitian.py` |
| Suggestion (explore) | Creative meal designer | 0.9 | `personas/dietitian.py` |
| Analyst | Nutrition calculator + food expert | 0.3 | `personas/analyst.py` |
| Pipeline Analyst | Internal harsh reviewer for suggestion refinement | 0.3 | `personas/pipeline_analyst.py` |
| Shopping | Professional shopping advisor | 0.6 | `personas/shopping.py` |
| Scheduler | Kitchen workflow expert (task decomposition) | 0.3 | `personas/scheduler.py` |

### Chat Persona (`build_chat_prompt`)

Used for everyday conversation via the WebSocket chat endpoint.

- **Tone**: warm, friendly breakfast buddy — talks like a friend, not a chef
- **Context depth**: last 3 meals, current ingredients, preferences, habits
- **Health rules**: injected silently, never mentioned to user
- **Behavior**: steers non-breakfast topics back gently, confirms ingredient updates
  naturally, learns preferences through conversation
- **Output**: free-form Turkish text; currently appends a JSON meal block when it
  judges the conversation is meal-relevant (parsed by frontend to render MealBlock).
  Planned change: chat persona should never produce meal blocks — only the Suggest
  button triggers them.

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
- **Fridge constraint**: must build the meal from current inventory. Small missing
  items may be noted as optional substitutes, but the meal must work with what's there.
- **Avoid list**: hard ban — never suggest avoided ingredients, suggest alternatives
- **Seasonality**: prefer seasonal produce (hint, not hard constraint)
- **Output**: short Turkish text (taste tips only, no prep steps, no nutrition table,
  no supplement notes) + JSON block with `menu_name`, `menu[]` (nested ingredients),
  `prep_time_min`, `nutrition_note` (one line). Prep details belong in Prep Timeline;
  nutrition details belong in Analyze.

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

All personas share formatting functions for ingredients, history, preferences,
habits, health rules, behavioral patterns, user profile, and supplements. These
are injected into template placeholders at runtime. Food knowledge data lives in
`backend/services/knowledge.py` and is shared by Suggestion, Analyst, and Shopping.

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
│   │   ├── favorite_ingredients.py ← /favorite-ingredients CRUD (staples list)
│   │   ├── favorites.py            ← /favorites CRUD endpoints
│   │   ├── health_rules.py        ← /health-rules CRUD with priority
│   │   ├── ingredients.py           ← /ingredients CRUD + /ingredients/groups
│   │   ├── meals.py                 ← /meals history + /meals/weekly
│   │   ├── preferences.py          ← /preferences + /preferences/habits
│   │   ├── profile.py             ← /profile + /profile/supplements CRUD
│   │   ├── ratings.py              ← /ratings CRUD endpoints (1-10 scale)
│   │   ├── kitchen.py             ← /kitchen appliance config CRUD
│   │   ├── sessions.py            ← /sessions chat session management
│   │   ├── shopping.py            ← /shopping list CRUD + bought flow
│   │   └── scheduler.py          ← /scheduler/plan prep timeline endpoint
│   │
│   ├── services/
│   │   ├── context.py               ← shared context loaders for LLM prompts
│   │   ├── llm.py                   ← Ollama streaming + FallbackLyricCycler
│   │   ├── scheduler.py             ← kitchen job-shop scheduler
│   │   ├── suggestion.py            ← backward-compat re-exports from personas/
│   │   ├── knowledge.py            ← shared food knowledge module
│   │   ├── pipeline.py             ← 3-step suggestion pipeline
│   │   ├── insights.py             ← behavioral pattern extraction
│   │   ├── nutrition.py             ← Open Food Facts integration
│   │   └── personas/               ← one file per LLM persona for easy editing
│   │       ├── chat.py             ← samimi kahvaltı arkadaşı
│   │       ├── dietitian.py        ← profesyonel diyetisyen
│   │       ├── analyst.py          ← nutrition lab / robot
│   │       ├── pipeline_analyst.py ← internal reviewer for suggestion refinement
│   │       ├── shopping.py         ← professional shopping advisor
│   │       └── scheduler.py       ← kitchen task decomposition for prep timeline
│   │
│   ├── models/
│   │   ├── ingredient.py            ← Pydantic models + INGREDIENT_GROUPS list
│   │   ├── kitchen.py              ← Pydantic models + KITCHEN_APPLIANCES list
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
│       │   ├── test_sessions.py     ← session management tests
│       │   ├── test_shopping.py    ← shopping list endpoint tests
│       │   ├── test_scheduler.py  ← scheduler endpoint tests
│       │   ├── test_kitchen.py   ← kitchen appliance endpoint tests
│       │   └── test_favorite_ingredients.py ← favorite ingredients tests
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
    │   ├── App.jsx                  ← tab navigation (Chat, Fridge, Preferences, Settings)
    │   ├── App.styles.js            ← App layout styles
    │   ├── test-setup.js            ← vitest setup (jest-dom matchers)
    │   ├── styles/
    │   │   └── common.js            ← shared style definitions (panelContainer, input, etc.)
    │   ├── components/
    │   │   ├── ChatInterface.jsx    ← main chat UI + supplement toggle bar
    │   │   ├── MealBlock.jsx        ← inline meal suggestion block in chat
    │   │   ├── MealEditor.jsx       ← shared meal editor (used everywhere)
    │   │   ├── DecidePanel.jsx      ← "Today I ate..." confirm + rate flow
    │   │   ├── SuggestButton.jsx    ← suggest button + long-press mode panel
    │   │   ├── WeeklySummary.jsx    ← weekly meals summary view
    │   │   ├── IngredientPanel.jsx  ← Fridge tab: groups, expiry, favorites, shopping
    │   │   ├── FavoriteIngredientsPanel.jsx ← favorite ingredients overlay panel
    │   │   ├── ShoppingListPanel.jsx ← persistent shopping list overlay
    │   │   ├── PreferencesPanel.jsx ← favorites, dislikes, habits, avoid list
    │   │   ├── KitchenSettings.jsx  ← kitchen appliance toggle grid (sub-page)
│   │   ├── SettingsPanel.jsx    ← profile, supplements, ratings, health rules, kitchen
    │   │   ├── LoginScreen.jsx      ← PIN auth screen
    │   │   └── *.styles.js          ← per-component style files
    │   ├── services/
    │   │   ├── api.js               ← backend API calls (REST + WebSocket)
    │   │   └── api.test.js          ← API service tests
    │   ├── utils/
    │   │   └── ingredients.js       ← formatIngredient, normalizeItem, UNITS,
    │   │                               resolveUnit, rememberUnit (unit memory)
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

---

## Future Ideas (Not Yet Implemented — Discuss First)

- **Ingredient icons** — visual icons next to ingredient names in the inventory list.
  Needs discussion on icon source (emoji, icon library, Open Food Facts images, etc.),
  storage approach, and fallback behavior before implementation.

- **LLM drink + food combo quality** — test whether the LLM personas handle combined
  drink and food suggestions well (e.g., çay + peynirli kahvaltı). If weak, may need
  prompt tuning or explicit drink pairing instructions in the suggestion persona.

- **Local nutrition dataset** — a small curated dataset for common Turkish breakfast
  ingredients to supplement Open Food Facts and reduce LLM estimation fallback usage.

- **Known ingredients/meals only** — don't allow user to add meals or ingredients that
  are not known, so user always eats known stuff. Allow users to enter custom
  ingredients (with values and use cases depending if LLM knows the word or not) and
  custom meals (consisting of known ingredients).
