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

**Everything ready at once.** The prep planner splits a menu into untimed prep (chop, slice) and timed tasks on appliances. The LLM only decomposes and estimates; `_build_plan` in `routers/scheduler.py` does the math: the longest timed task sets the total time and every other task starts at `total − duration`, so all food finishes together. The planner gets only what the menu lists: each dish comes with its `method` in brackets after its name and is planned that way, items served as they are get no cooking, and the prompt's example plan is placeholders only (the 7B model copied its food into real plans). User's configured appliances (from Kitchen Settings) are injected into all LLM prompts.

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

**Done:** Ingredient groups (11 fixed groups incl. 🫙 Pantry, English names), fridge-only enforcement (code check after the draft), expiry tracking, favorite ingredients (staples list), shopping list, delete confirm redesign, kitchen appliances settings, multi-item menu format, shared MealEditor, unit dropdown with smart defaults, simplified suggestion text, overlay edit pattern across all panels, explore mode, shopping assistant persona, weekly nutrition review, language toggle (English default + Turkish option), chat meal blocks only from the Suggest button, five color themes, Markdown in chat replies, fridge readiness badges on chat cards and favorites, "Today I ate" rework (Confirm waits until nothing is missing, Ate out, ⭐ Save, kept draft), units that follow the language setting, shopping suggestions as specific buyable products (date and country aware, structured outputs, code dedupe so Suggest More never repeats).

**Remaining:** Habit onboarding, auth hardening (salted slow PIN hashing, 6+ digit PIN minimum, login rate limiting).

---

## Meal Format

LLM returns a full menu, not a single dish:

```json
{
  "menu_name": "Klasik Kahvaltı",
  "menu": [
    { "name": "Menemen", "method": "Biberi ve domatesi kavur, yumurtaları ekleyip karıştır", "ingredients": [
        { "name": "Yumurta", "amount": 2, "unit": "adet", "prep": "çırpılmış" }
    ]},
    { "name": "Beyaz peynir", "amount": 50, "unit": "g", "ingredients": [] }
  ],
  "prep_time_min": 15,
  "nutrition_note": "Protein ve yağ dengesi iyi."
}
```

- Complex dish: no top-level `amount`, has `ingredients[]`
- Simple item: has `amount` + `unit`, `ingredients: []`
- A dish may carry an optional `method`: its main steps in one short line, in the reply language ("Hard-boil the eggs, peel, slice into the bread"). It is stored with the dish in `menu_items` (older meals have none), and the prep plan gets "- Egg sandwich (Hard-boil the eggs, …): Egg (2 pcs), Bread (2 slice)"
- A dish ingredient may carry optional `prep` words ("rolled", "chopped"): the name stays exactly the fridge name, and the prep plan gets "Oats (1 glass, rolled)"
- MealEditor shows each dish's method and prep words behind an ℹ️ button beside the time and id
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

**Suggestion persona:** outputs short text (taste tips only — no prep steps, no nutrition table, no supplement notes) + JSON meal block. Must build meals from the fridge inventory only, basics like salt and oil included; a missing recipe item may be replaced with an inventory item, never with something outside it. A simple item is one fridge item served as it is; anything cooked, combined or with a sauce is a dish with its ingredients and a one-line `method`, which carries the dish's design to the prep plan. The prompt's JSON example shows the format only (placeholders), because the 7B model copies a full example menu.

**Suggestion pipeline:** Draft → Analyst review (at most three concrete changes with fridge items) + code fridge check (`services/fridge.py`) → Refine (one pass, keeps everything the feedback doesn't touch). Missing ingredients go to the refine step as the first feedback point. The review may only improve the meal: if code counts more fridge misses or unknown units in the final than in the draft, the user gets the draft, so the final is sent once that check is done instead of streamed. Code never removes items from a suggested menu: something the user doesn't have keeps its yellow mark so they can obtain it, and better menus come from the prompts. Progress sent via WebSocket `{type: 'progress'}`.

**Shopping persona:** suggests products you can buy, never dishes (a dish becomes its missing ingredients). Names are plain and specific, and every word names the product: "Frozen strawberries" is a different item from "Strawberries", while filler like "fresh" doesn't belong in a name. The reply is constrained by Ollama structured outputs (`SUGGESTIONS_SCHEMA` in `services/shopping.py`, sent by `chat_json` in `services/llm.py`; needs Ollama 0.5+), and the raw reply is logged when it still can't be parsed. Code then drops anything in the fridge, on the shopping list, already shown or on the avoid list by exact name (`same_name` in `services/fridge.py`: case, Turkish letters and plurals only), and asks once more when a whole reply was repeats. Code also drops names that aren't one product ("Leafy greens (e.g. spinach)", "X or Y"; the prompt asks for alternatives as separate items next to each other) and the user's own dishes (`dish_names`: meal names and menu items made with ingredients, from all logged and favorite meals; simple items stay products). That filter is a safety net: the prompt asks for a dish's missing ingredients instead of the dish. The request message (`shopping_request`) names the reply language and, for Suggest More, the items already shown: the 7B model follows the last message better than the system prompt.

**Suggestion + Analyst + Shopping** share `backend/services/knowledge.py`.

**Prompt style:** state each rule once, in the prompt that owns it, as a positive instruction with a short reason, not a growing list of bans and special cases. Anything code can verify (fridge membership, JSON shape) is checked in code, not by asking another persona to police it.

**Prompt test:** `backend/tools/prompt_check.py` runs the real suggestion pipeline (or, with `--persona shopping`, Suggest Shopping then Suggest More) for the sample users in `tools/prompt_samples.py` (en, tr, mixed, demo, sparse, vegan), or with `--persona plan` the prep planner for the menus in `PLAN_CASES` (a hard-boiled egg sandwich among them), against an Ollama server and scores the replies in code. For suggestions it scores the draft and the final (meal JSON, missing fridge items, renamed ones such as "White cheese (peynir)" or "Simit with tahini", units the app can't show, Turkish words in English replies, distinct menus; the review's feedback is logged too); for shopping it flags dishes, vague names, repeats the dedupe has to drop, and Turkish words in English replies; for plans it flags food the menu doesn't list, a dish cooked another way than its method says (fry vs boil), and Turkish words in English replies. Run it before and after a prompt change with a `--note` (`docs/SETUPALL.md`, BONUS C): every test is logged in the git-ignored `tools/runs/` (replies, prompts sent, `history.jsonl`) and compared with the best earlier one, so keep a change only when it doesn't score worse. The pipeline yields `draft` and `review` events for it, which chat ignores. When the suggestion context gains a field, add it to the samples (a test runs every sample through the pipeline).

---

## Key Rules

- **Health rules**: injected into every LLM prompt silently. Never surface them to the user.
- **Avoid list**: hard ban. Never suggest avoided ingredients.
- **Fridge constraint**: suggestions use only the inventory. Nothing is assumed: basics (salt, oil, spices) and long-life items (flour, sesame, oats…) are logged like anything else, usually in the 🫙 Pantry group. A planned Fridge quick-add button will make logging them easy. Water is a utility like electricity and gas: recipes may list it and the check skips it. The suggestion prompt doesn't mention water, so the model isn't drawn to serving it on its own. Ingredient names in the meal JSON must match the inventory as written, one item per name (a cut or form like "rolled" goes in the ingredient's `prep`), so the code check can compare them. The check matches one way: a meal name may be shorter than a fridge name ("Peynir" for "Beyaz peynir"), never longer ("Poached egg" isn't "Egg").
- **Date and country**: today's date and the optional Country from Settings → Profile (`user_profiles.country`, list in `utils/countries.js`) go into the shopping and suggestion prompts (`format_today`), so "in season" means something. The profile text the analysts read leaves the country out.
- **CORS**: configurable via `CORS_ORIGINS` env var (comma-separated).
- **Demo user**: only created when `DEMO_USER=true` (empty PIN). A newly created demo account gets a starter fridge (`DEMO_FRIDGE` in `models/ingredient.py`, basics included). Never enable it on a reachable instance.
- **Language**: the UI is English only; the setting changes AI replies. User data is often Turkish and pulls a 7B model toward Turkish, so every user-facing prompt ends with a `FINAL REMINDER` restating the language directive. Code-built text in replies (e.g. prep plan labels) follows the same setting, and so do units.
- **Theme**: Settings → Theme (orange default, then green, teal, blue, purple: hues spread around the wheel, each nudged warm, all WCAG AA) changes only `--accent`, `--accent2`, `--secondary` / `--secondary-soft` and the assistant bubble `--bubble` (`index.css`, `:root[data-theme=…]`). Use those variables or `secondaryColor`, never a hard-coded accent hex. Semantic colors never follow the theme: red (`colors.danger*`) means delete/remove, health-rule priorities are a traffic light (red top priority, yellow care a lot, green don't really care), plus expiry warnings and stars. Saved as the `theme` preference and cached in `localStorage` (`utils/theme.js`).
- **App settings vs food preferences**: settings stored as preferences (`SETTING_KEYS` in `services/context.py`: language, theme, weekly-summary toggle) are kept out of prompts.
- **Line endings**: `.gitattributes` normalizes to LF in repo, CRLF on Windows checkout.

---

## Shared Components

**MealEditor** (`frontend/src/components/MealEditor.jsx`) — used everywhere (chat, favorites, meal history, "Today I ate"). Key props: `menuMode`, `onFavorite(currentMeal)`, `extraActions(buildCurrentMeal) => ReactNode`. The function form of `extraActions` gives callers access to live editor state. `checkFridge` underlines ingredients that aren't in the fridge (via `POST /ingredients/check`, same matching as the pipeline) in yellow; tapping one marks it as obtained for this meal (green, stored as `meal.obtained`). `onMissingChange(names)` reports what's still missing and not obtained; `onChange(meal)` reports live state; `extraActions(build, { markAllObtained })`. On in chat meal details (marks are saved with the card and carry into "Today I ate", not back) and in "Today I ate", where Confirm waits until nothing is missing, Ate out marks every missing item as obtained (no logging), ⭐ Save keeps the menu in favorites, and the draft survives closing and Back from rating until another chat meal is selected. Chat cards and Favorites rows show readiness on their icon (`ReadinessIcon` + `hooks/useMealReadiness.js`: yellow = missing, green = ready). Favorites are templates: their editor shows the yellow underline only (`canMarkObtained={false}`). The plain Save button only appears when the caller passes `onSave`. Callers must pass a stable `meal` object: a new object resets the editor's edits.

**Units** — source of truth: `backend/models/units.py` (`UNIT_PAIRS`: each English unit paired 1-1 with its Turkish match, plus `UNIT_ALIASES` like "gr" → g), mirrored in `frontend/src/utils/ingredients.js`. Edit both locations. Spoons and glasses have one fixed size in both languages (`UNIT_ML`: tsp 5 ml … glass / su bardağı 200 ml), stated in the suggestion prompt and shown only in the editor's open unit list, so an amount means the same in either language; "cup" is deliberately not a unit (a US cup is 240 ml). Units follow the AI language (English list by default, Turkish in Turkish mode): the suggestion prompt lists them, and stored meals keep their units as written while known ones are shown in the current language (`localizeUnit`; the prep-plan input does the same). The frontend reads the language from `utils/language.js` via `useLanguage()`, set at login and by the Settings toggle.

**Unit memory** (`frontend/src/utils/ingredients.js`) — `unitsFor(language)`, `resolveUnit(name)` (localStorage memory → smart keyword default from Turkish or English names → pcs / adet, shown in the current language), `rememberUnit(name, unit)`.

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
│   ├── tools/
│   │   ├── prompt_check.py          ← prompt test: real pipeline vs Ollama, replies scored in code
│   │   └── prompt_samples.py        ← sample users (English and Turkish fridges) for it
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
│   │   ├── fridge.py                ← fridge check: draft ingredients vs inventory; exact name match
│   │   ├── shopping.py              ← shopping reply schema, parser + dedupe
│   │   ├── suggestion.py            ← stream_response + persona re-exports
│   │   └── llm.py                   ← Ollama streaming + lyric fallback
│   └── models/
│       ├── ingredient.py            ← INGREDIENT_GROUPS (source of truth)
│       ├── kitchen.py               ← KITCHEN_APPLIANCES (source of truth)
│       ├── units.py                 ← UNIT_PAIRS English ↔ Turkish (source of truth)
│       └── meal.py                  ← MealLog, Meal (includes menu_items)
└── frontend/src/
    ├── App.jsx                      ← tab nav (Chat, Fridge, Preferences, Settings)
    ├── utils/ingredients.js         ← ingredient helpers, units per language + unit memory
    ├── utils/language.js            ← AI language store (cached per device, like the theme)
    ├── utils/countries.js           ← Country list for Settings → Profile
    ├── styles/common.js             ← shared styles
    ├── services/api.js              ← all REST + WebSocket calls
    ├── hooks/useVoice.js            ← Web Speech API
    ├── hooks/useLanguage.js         ← current AI language, re-renders on change
    ├── hooks/useMealReadiness.js    ← fridge readiness for a meal (card + favorites badge)
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
