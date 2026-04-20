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

**Prep time is kitchen time.** The scheduler treats the kitchen like a small factory — appliances are resources, food items are jobs. Goal is to minimize total wall-clock time by running things in parallel. This is a job-shop scheduling problem. Greedy earliest-start algorithm. User's configured appliances (from Kitchen Settings) are injected into all LLM prompts.

**Local-first, free forever.** Primary LLM is Ollama on the user's own hardware. Song lyric fallback when unreachable.

**The system learns.** Stated habits are a warm prior. Actual behavior updates what gets recommended.

---

## Tech Stack

| Layer | Choice |
|---|---|
| Frontend | React PWA (Vite) |
| Backend | Python / FastAPI |
| Local LLM | Ollama + Llama 3.1 8B |
| LLM Fallback | Song lyric cycling |
| Database | SQLite (aiosqlite) |
| Voice | Web Speech API |
| Nutrition | Open Food Facts API |
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

Chat with Ollama, ingredient inventory, meal suggestions, meal history, multi-user auth, session persistence, voice input/output, meal blocks in chat, kitchen scheduler, ratings, preferences (favorites/dislikes/habits/avoid), suggest button with modes, "Today I ate" flow, nutrition analysis, 3-step suggestion pipeline, user profiles, supplements, health rules, weekly summary, Settings page.

### Phase 3 (IN PROGRESS)

**Done:** Ingredient groups (10 fixed Turkish groups), expiry tracking, favorite ingredients (staples list), shopping list, delete confirm redesign, kitchen appliances settings, multi-item menu format, shared MealEditor, unit dropdown with smart defaults, simplified suggestion text, overlay edit pattern across all panels.

**Remaining:** Habit onboarding, explore mode ("suggest something new"), shopping assistant persona, weekly nutrition summary, language toggle (English default + Turkish option), chat meal block behavior fix (blocks should only come from Suggest button), fridge constraint enforcement in suggestions.

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

All in `backend/services/personas/`. Prompts are in English with "Always respond in Turkish". A language toggle (English default) is planned — don't remove the Turkish path.

| Persona | Job | Temp | File |
|---|---|---|---|
| Chat | Casual breakfast buddy | default | `chat.py` |
| Suggestion | Creative meal designer (comfort/explore/quick modes) | 0.6/0.9 | `dietitian.py` |
| Analyst | Nutrition calculator | 0.3 | `analyst.py` |
| Pipeline Analyst | Internal reviewer for suggestion refinement | 0.3 | `pipeline_analyst.py` |
| Shopping | Professional shopping advisor | 0.6 | `shopping.py` |
| Scheduler | Kitchen task decomposer | 0.3 | `scheduler.py` |

**Chat persona:** responds in free-form text. Currently appends a JSON meal block when it judges the message is meal-relevant — this is a known issue. Planned fix: meal blocks only from the Suggest button, never from chat.

**Suggestion persona:** outputs short Turkish text (taste tips only — no prep steps, no nutrition table, no supplement notes) + JSON meal block. Must build meals from existing fridge inventory. Small substitutes for missing items are allowed.

**Suggestion pipeline:** Draft → Analyst review → Refine (max 2 rounds). Progress sent via WebSocket `{type: 'progress'}`.

**Suggestion + Analyst + Shopping** share `backend/services/knowledge.py`.

---

## Key Rules

- **Health rules**: injected into every LLM prompt silently. Never surface them to the user.
- **Avoid list**: hard ban. Never suggest avoided ingredients.
- **Fridge constraint**: suggestions must use current inventory. Substitutes OK for small gaps.
- **Nutrition API**: always set `User-Agent: "breakFAST/1.0 (personal project)"` on Open Food Facts requests.
- **CORS**: configurable via `CORS_ORIGINS` env var (comma-separated).
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
├── start.bat                        ← Windows launcher (opens backend + frontend)
├── backend/
│   ├── main.py                      ← FastAPI entry, lifespan init_db
│   ├── database.py                  ← SQLite schema + migrations
│   ├── auth.py                      ← JWT auth
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
│   │   ├── scheduler.py             ← /scheduler/plan
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
│   │   ├── llm.py                   ← Ollama streaming + lyric fallback
│   │   ├── scheduler.py             ← greedy job-shop scheduler
│   │   └── nutrition.py             ← Open Food Facts integration
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

**Makespan** — total wall-clock time from first task to last in a cooking schedule.

**Warm prior** — stated habit treated as a starting assumption, updated by observed behaviour.

**Comfort / Explore modes** — comfort optimises for familiar meals; explore finds novel meals adjacent to the user's taste profile.
