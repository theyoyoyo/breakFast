# break FAST — Project Intelligence File

Read this file before touching any code. It captures product decisions, rules, and architectural choices that aren't obvious from the code alone.

---

## What Is break FAST?

An AI-powered breakfast planner for home/trusted circle use. It knows each user — their ingredients, health context, habits, and kitchen — and uses that to suggest the richest, healthiest, most efficiently prepared breakfast each morning with minimal friction.

Multiple users share one instance, each fully isolated. Auth is simple (pin/name), managed by admin CLI. Accessible via Tailscale.

---

## Core Design Principles

**Reduce morning decision fatigue.** The app suggests proactively. If it needs info, it asks one question at a time.

**Health-aware, silently.** Health rules are per-user, stored in DB, injected into prompts at runtime. Never mentioned to the user. The app just makes good choices.

**Everything ready at once.** The prep planner splits a menu into untimed prep (chop, slice) and timed tasks on appliances. The LLM only decomposes and estimates; `_build_plan` in `routers/scheduler.py` does the math: the longest timed task sets the total time and every other task starts at `total − duration`, so all food finishes together. User's configured appliances (from Kitchen Settings) are injected into all LLM prompts.

**Local-first, free forever.** Primary LLM is Ollama on the user's own hardware. Song lyric fallback when unreachable.

**The system learns.** Stated habits are a warm prior. Actual behavior updates what gets recommended.

---

## Tech Stack

| Layer | Choice |
|---|---|
| Frontend | React PWA (Vite) |
| Backend | Python / FastAPI |
| Local LLM | Ollama + Qwen 2.5 7B (`OLLAMA_MODEL`) |
| LLM Fallback | Song lyric cycling |
| Database | SQLite (aiosqlite) |
| Voice | Web Speech API |
| Nutrition | LLM Analyst persona (estimates, cached per meal) |
| Remote Access | Tailscale |

---

## Architecture

```
[Phone / Desktop — browser]
         |  HTTP / WebSocket
         v
[FastAPI Backend — third PC]
   |               |
   v               v
[Ollama]    [Song lyric fallback]
   |
   v
[SQLite — breakFAST.db]
```

---

## Features

Phase 1 and Phase 2 are complete. Phase 3 is in progress.

### Phase 1 + 2 (COMPLETE)

Chat with Ollama, ingredient inventory, meal suggestions, meal history, multi-user auth, session persistence, voice input, meal blocks in chat, kitchen prep planner, ratings, preferences (favorites/dislikes/habits/avoid), suggest button with modes, "Today I ate" flow, nutrition analysis, 3-step suggestion pipeline, user profiles, supplements, health rules, weekly summary, Settings page.

### Phase 3 (IN PROGRESS)

**Done:** Ingredient groups (10 fixed Turkish groups), expiry tracking, favorite ingredients (staples list), shopping list, delete confirm redesign, kitchen appliances settings, multi-item menu format, shared MealEditor, unit dropdown with smart defaults, simplified suggestion text, overlay edit pattern across all panels, explore mode, shopping assistant persona, weekly nutrition review, language toggle (English default + Turkish option), chat meal blocks only from the Suggest button.

**Remaining:** Habit onboarding, stricter fridge constraint enforcement in suggestions, auth hardening (salted slow PIN hashing, 6+ digit PIN minimum, login rate limiting).

---

## Meal Format

LLM returns a full menu, not a single dish:

```json
{
  "menu_name": "Klasik Kahvaltı",
  "menu": [
    { "name": "Menemen", "ingredients": [
        { "name": "Yumurta", "amount": 2, "unit": "adet" }
    ]},
    { "name": "Beyaz peynir", "amount": 50, "unit": "g", "ingredients": [] }
  ],
  "prep_time_min": 15,
  "nutrition_note": "Protein ve yağ dengesi iyi."
}
```

- Complex dish: no top-level `amount`, has `ingredients[]`
- Simple item: has `amount` + `unit`, `ingredients: []`
- `isSimpleItem(item)` = `item.amount != null`
- DB column `menu_items TEXT` on `meal_history`, `suggested_meals`, `favorite_meals`
- Old flat-format meals still work via `normalizeMeal()` in frontend

---

## LLM Personas

All in `backend/services/personas/`. Prompts are in English; the response language follows the user's setting (English default, Turkish option) — don't remove the Turkish path.

| Persona | Job | Temp | File |
|---|---|---|---|
| Chat | Casual breakfast buddy | default | `chat.py` |
| Suggestion | Creative meal designer (favorites/explore modes) | 0.6/0.9 | `dietitian.py` |
| Analyst | Nutrition calculator | 0.3 | `analyst.py` |
| Pipeline Analyst | Internal reviewer for suggestion refinement | 0.3 | `pipeline_analyst.py` |
| Shopping | Professional shopping advisor | 0.6 | `shopping.py` |
| Scheduler | Kitchen task decomposer | 0.3 | `scheduler.py` |
| Weekly Analyst | Holistic 7-day nutrition review (4 scores) | default | `weekly_analyst.py` |

**Chat persona:** responds in plain text only. Meal blocks come only from the Suggest button, never from chat.

**Suggestion persona:** outputs short text (taste tips only — no prep steps, no nutrition table, no supplement notes) + JSON meal block. Must build meals from existing fridge inventory. Small substitutes for missing items are allowed.

**Suggestion pipeline:** Draft → Analyst review → Refine (one pass). Progress sent via WebSocket `{type: 'progress'}`.

**Suggestion + Analyst + Shopping** share `backend/services/knowledge.py`.

---

## Key Rules

- **Health rules**: injected into every LLM prompt silently. Never surface them to the user.
- **Avoid list**: hard ban. Never suggest avoided ingredients.
- **Fridge constraint**: suggestions must use current inventory. Substitutes OK for small gaps.
- **CORS**: configurable via `CORS_ORIGINS` env var (comma-separated).
- **Demo user**: only created when `DEMO_USER=true` (empty PIN). Never enable it on a reachable instance.
- **Line endings**: `.gitattributes` normalizes to LF in repo, CRLF on Windows checkout.

---

## Shared Components

**MealEditor** (`frontend/src/components/MealEditor.jsx`) — used everywhere (chat, favorites, meal history, "Today I ate"). Key props: `menuMode`, `onFavorite(currentMeal)`, `extraActions(buildCurrentMeal) => ReactNode`. The function form of `extraActions` gives callers access to live editor state.

**Unit memory** (`frontend/src/utils/ingredients.js`) — `UNITS` list, `resolveUnit(name)` (localStorage memory → smart keyword default → 'adet'), `rememberUnit(name, unit)`.

**Ingredient groups** — source of truth: `backend/models/ingredient.py` (INGREDIENT_GROUPS), mirrored in `IngredientPanel.jsx`. Edit both locations to change groups.

---

## File Structure

```
breakFAST/
├── CLAUDE.md
├── setup.bat                        ← Windows first-time setup (deps + model pull)
├── start.bat                        ← Windows launcher (opens backend + frontend)
├── start-server.bat                 ← Windows production launcher (FastAPI serves the build)
├── docs/                            ← full server setup guide + feature specs
├── backend/
│   ├── main.py                      ← FastAPI entry, lifespan init_db
│   ├── database.py                  ← SQLite schema + migrations
│   ├── auth.py                      ← PIN hashing + in-memory bearer tokens
│   ├── manage.py                    ← admin CLI (add/list/delete users)
│   ├── db_helpers.py                ← reusable DB query helpers
│   ├── routers/
│   │   ├── chat.py                  ← WebSocket /chat
│   │   ├── meals.py                 ← /meals history
│   │   ├── ingredients.py           ← /ingredients CRUD + groups
│   │   ├── favorites.py             ← /favorites (saved meals)
│   │   ├── favorite_ingredients.py  ← /favorite-ingredients (staples)
│   │   ├── shopping.py              ← /shopping list
│   │   ├── analyst.py               ← /analyst/analyze
│   │   ├── scheduler.py             ← /scheduler/plan (finish-together prep plan)
│   │   ├── kitchen.py               ← /kitchen appliance config
│   │   ├── sessions.py              ← /sessions
│   │   ├── profile.py               ← /profile + supplements
│   │   ├── ratings.py               ← /ratings
│   │   ├── health_rules.py          ← /health-rules
│   │   ├── preferences.py           ← /preferences + habits
│   │   └── auth.py                  ← /auth/login
│   ├── services/
│   │   ├── personas/                ← one file per LLM persona
│   │   ├── pipeline.py              ← 3-step suggestion pipeline
│   │   ├── context.py               ← shared context loaders for prompts
│   │   ├── knowledge.py             ← shared food knowledge
│   │   ├── insights.py              ← behavioral pattern extraction
│   │   ├── suggestion.py            ← stream_response + persona re-exports
│   │   └── llm.py                   ← Ollama streaming + lyric fallback
│   └── models/
│       ├── ingredient.py            ← INGREDIENT_GROUPS (source of truth)
│       ├── kitchen.py               ← KITCHEN_APPLIANCES (source of truth)
│       └── meal.py                  ← MealLog, Meal (includes menu_items)
└── frontend/src/
    ├── App.jsx                      ← tab nav (Chat, Fridge, Preferences, Settings)
    ├── utils/ingredients.js         ← ingredient helpers + unit memory
    ├── styles/common.js             ← shared styles
    ├── services/api.js              ← all REST + WebSocket calls
    ├── hooks/useVoice.js            ← Web Speech API
    └── components/
        ├── ChatInterface.jsx        ← main chat UI
        ├── MealBlock.jsx            ← inline meal block in chat
        ├── MealEditor.jsx           ← shared meal editor (used everywhere)
        ├── DecidePanel.jsx          ← "Today I ate" flow
        ├── SuggestButton.jsx        ← suggest button + mode picker
        ├── IngredientPanel.jsx      ← Fridge tab
        ├── PreferencesPanel.jsx     ← favorites, dislikes, habits, avoid
        ├── SettingsPanel.jsx        ← profile, supplements, health rules, history
        ├── FavoritesPanel.jsx       ← saved meals panel
        ├── WeeklySummary.jsx        ← weekly meals + nutrition summary
        └── KitchenSettings.jsx      ← appliance toggle grid
```

---

## Glossary

**Makespan** — total wall-clock time from first task to last in a cooking plan.

**Warm prior** — stated habit treated as a starting assumption, updated by observed behaviour.

**Favorites / Explore modes** — favorites optimises for familiar meals; explore finds novel meals adjacent to the user's taste profile.
