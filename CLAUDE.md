# break FAST — Project Intelligence File

Read this file before touching any code. It captures product decisions, rules, and architectural choices that aren't obvious from the code alone.

---

## What Is break FAST?

An AI-powered breakfast planner for home/trusted circle use. It knows each user — their ingredients, health context, habits, and kitchen — and uses that to suggest the richest, healthiest, most efficiently prepared breakfast each morning with minimal friction.

Multiple users share one instance, each fully isolated. Auth is a name and a PIN (salted scrypt hashes, rate-limited logins), managed by admin CLI. Accessible via Tailscale.

---

## Core Design Principles

**Reduce morning decision fatigue.** The app suggests proactively. If it needs info, it asks one question at a time.

**Health-aware, silently.** Health rules are per-user, stored in DB, injected into prompts at runtime. Never mentioned to the user. The app just makes good choices.

**Everything ready at once.** The prep planner breaks each cooked dish into its real steps, in order, one action each (usually a few): the action with the menu's ingredients and amounts, its minutes, hands-on (whisk, chop, flip, plate) or waiting (boil, toast, bake), and an optional appliance from the user's list. The LLM only decomposes and estimates; `_build_plan` in `routers/scheduler.py` does the math. It schedules backwards from the finish so the dishes are ready together: each dish's steps stay in order, one cook does the hands-on steps one at a time, an appliance holds one step (the Stove two pans), and waiting steps need no cook, so other dishes' hands-on steps fill them. A dish's consecutive hands-on steps are one block, placed whole, so the cook switches dishes only at waits: another dish's block fills a wait or goes before or after it, a wait may start during a block's last step (put the bread in while the omelette sets) but not earlier in it, so the list never splits a block, and on a tie the dish just placed goes on. Whole blocks can make the one-pass plan much longer, so a short search (limited discrepancy, at most `_SEARCH_NODES` placements, off the event loop) tries other orders and keeps a shorter plan, or one as short where hot food sits less (`_hot_sitting`: a dish made with a hot appliance, `hot` in `KITCHEN_APPLIANCES`, waiting after it's done, and food from a hot step such as toast waiting for its dish's next step; a dish made without one, like a chia pudding, keeps and may be made first), then one with fewer switches; on random menus a plan is at most a few minutes longer than one that splits blocks (#152). Estimates code can't use get a default (a missing or non-positive minute count, an appliance outside the user's list, a missing hands_on). The plan is one list in time order under `⏱ Plan (N min)`: a time line (h:mm) names its dish before the step, the dish's steps that follow right after it sit under it as `↳` lines, a dish stops at a wait for another dish's steps and picks up again later (on a tie in the list a wait comes first, so the block it starts with stays together), waiting steps show their minutes and appliance, and the Ready line ends it. Code keeps colons out of dish names, so the app reads a time line's dish as the text before its first colon and colors it (`PrepPlanText`). Cached plans (`meal_history.schedule`) keep their old text. The planner gets only what the menu lists: each dish comes with its `method` in brackets after its name and is planned that way, items served as they are get no steps, and the prompt's example plan is placeholders only (the 7B model copied its food into real plans). User's configured appliances (from Kitchen Settings) are injected into all LLM prompts.

**Local-first, free forever.** Primary LLM is Ollama on the user's own hardware. Song lyric fallback when unreachable.

**The system learns.** Stated habits are a warm prior. Actual behavior updates what gets recommended.

---

## Tech Stack

| Layer | Choice |
|---|---|
| Frontend | React PWA (Vite) |
| Backend | Python / FastAPI |
| Local LLM | Ollama + Qwen 2.5 7B (`OLLAMA_MODEL`), 8192-token context (`OLLAMA_NUM_CTX`) |
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

**Chat sync across devices:** `services/chat_sync.py` keeps each user's open chat sockets in memory (one server process, no polling) and drops a socket on disconnect. When a session's messages change (a chat reply is saved, or a message is saved or edited over REST: meals sent to chat, analysis and prep plan results, meal card edits, which rewrite the message's JSON meal block, a card's saved "Today I ate" version, and the selected meal card), the server sends `{type: 'session_updated', session_id}` to that user's sockets only. A reply skips the socket that asked, and tokens never go to other devices. `ChatInterface` reloads the chat on screen on that push, when the page becomes visible again, and when its socket opens. A reload waits for a streaming reply or a running analysis, and keeps the draft and unchanged cards. A reply whose device drops mid-stream still finishes and is saved. The selected meal card (today's meal) is the same on every device: `chat_sessions.selected_message_id`, set with `PUT /sessions/{id}/selected` (a tap on a selected card's box unselects it), by a new suggestion, by a meal sent to chat (`select: true` on its POST), and cleared when the meal is logged; GET messages marks it `selected`.

Other changes send a small notice through `notify_user`: a supplement change or a pill marked for today sends `{type: 'supplements_updated'}`, and a shopping suggestions list change (bringing back removed suggestions included) `{type: 'shopping_suggestions_updated'}`. All tabs stay mounted, so the chat socket is open while the app is: `ChatInterface` passes every notice that isn't about the chat to the rest of the app as one window event (`hooks/useSyncNotice.js`: `emitSyncNotice`, `useSyncNotice(types, handler)`), plus `{type: 'sync_connected'}` when its socket opens, so a panel can catch up on what it missed. The 💊 list reloads on a supplements notice, when the socket opens and when the page becomes visible; Settings reloads only its supplement list, so an unsaved profile edit stays. The Fridge tab reloads its suggestions list the same way, and Settings its count of removed suggestions. That list starts collapsed under a theme-colored bar as big as Suggest Shopping (title and count in the middle, ▲ while closed and ▼ while open at the right); while open, two helpers at the left check or uncheck every item and clear the list after an "Are you sure?" (cleared items aren't left out of later suggestions, unlike ×).

---

## Features

Phase 1 and Phase 2 are complete. Phase 3 is in progress.

### Phase 1 + 2 (COMPLETE)

Chat with Ollama, ingredient inventory, meal suggestions, meal history, multi-user auth, session persistence, voice input, meal blocks in chat, kitchen prep planner, ratings, preferences (favorites/dislikes/habits/avoid), suggest button with modes, "Today I ate" flow, nutrition analysis, 3-step suggestion pipeline, user profiles, supplements, health rules, weekly summary, Settings page.

### Phase 3 (IN PROGRESS)

**Done:** Ingredient groups (11 fixed groups incl. 🫙 Pantry, English names), fridge-only enforcement (code check after the draft), expiry tracking, favorite ingredients (staples list), shopping list, delete confirm redesign, kitchen appliances settings, multi-item menu format, shared MealEditor, unit dropdown with smart defaults, simplified suggestion text, overlay edit pattern across all panels, explore mode, shopping assistant persona, weekly nutrition review, language toggle (English default + Turkish option), chat meal blocks only from the Suggest button, five color themes, Markdown in chat replies, fridge readiness badges on chat cards and favorites, "Today I ate" rework (Confirm waits until nothing is missing, a dish's name marks its items, ☆ favorites, Skip on the rating step), units that follow the language setting, shopping suggestions as specific buyable products (date and country aware, structured outputs, code dedupe so Suggest More never repeats, a random share of the fridge and taste hints per press so they follow each user), supplements synced across devices and editable in Settings (✏️), shopping suggestions kept on the server per user and synced (Send to List moves only the checked items, × leaves an item out of suggestions for 7 days, ▲/▼ hides the list, select all and clear all), "Today I ate" Save stored with the chat card and synced, the selected meal card synced, a Settings profile that fits phones with country codes, tab names beside the app name (Preferences, Favorites, Settings) and favorite ids in Favorites, favorites mode weighing saved favorite meals, staples and ratings with the rest of the user's taste, auth hardening (salted scrypt PIN hashes, 6-10 digit PINs, login rate limiting), prep plans that keep a dish's hands-on steps together (blocks, switches only at waits), bringing back removed shopping suggestions from Settings → AI settings, and a shopping list with the suggestions list's helpers (select all, Delete all), "Are you sure?" before both Delete all buttons, the best before date (BBD) inline on a checked item's row and a × per item (not bought yet, so no trash can), a built-in food list that puts new Fridge items in their group (about 600 foods with English and Turkish names; the user's own picks win and are kept), and suggestions that follow the chat in every step (the server reads the session's typed messages and meal cards, the latest wins).

**Remaining:** Habit onboarding.

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
  "prep_time_min": 15
}
```

- Complex dish: no top-level `amount`, has `ingredients[]`
- Simple item: has `amount` + `unit`, `ingredients: []`
- A dish may carry an optional `method`: its main steps in one short line, in the reply language ("Hard-boil the eggs, peel, slice into the bread"). It is stored with the dish in `menu_items` (older meals have none), and the prep plan gets "- Egg sandwich (Hard-boil the eggs, …): Egg (2 pcs), Bread (2 slice)". The draft prompt doesn't ask for it (with a method rule the prompt test scored worse: more renamed items and unknown units); the pipeline's reviser writes it for every dish through structured outputs (#121, #122)
- `nutrition_note` is no longer asked for (nothing showed it); older meals keep theirs
- A dish ingredient may carry optional `prep` words ("rolled", "chopped"): the name stays exactly the fridge name, and the prep plan gets "Oats (1 glass, rolled)"
- MealEditor shows each dish's method and prep words behind an ℹ️ button beside the prep time
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
| Pipeline Analyst | Internal reviser: returns the fixed meal (structured outputs) | 0.3 | `pipeline_analyst.py` |
| Shopping | Professional shopping advisor | 0.6 | `shopping.py` |
| Scheduler | Kitchen step decomposer (steps per dish) | 0.3 | `scheduler.py` |
| Weekly Analyst | Holistic 7-day nutrition review (4 scores) | default | `weekly_analyst.py` |

**Chat persona:** responds in plain text only. Meal blocks come only from the Suggest button, never from chat.

**Suggestion persona:** drafts the menu (its own text + JSON meal block; the text isn't shown) and, in the pipeline's last step, writes the short reply text from the final meal alone (`build_present_prompt`: the menu name, one sentence, an optional taste tip; only items on the menu, no nutrition claims or prep steps). Must build meals from the fridge inventory only, basics like salt and oil included; a missing recipe item may be replaced with an inventory item, never with something outside it. A simple item is one fridge item served as it is; anything cooked, combined or with a sauce is a dish with its ingredients. The prompt's JSON example shows the format only (placeholders), and the rules carry no example dish or ingredient lists, because the 7B model copies examples into menus. Favorites mode asks for a menu that fits the user's taste, weighing every hint together without tying it to one: it lists the newest 10 meals saved in Favorites (`fetch_favorite_meals` in `services/context.py`, each as its name and one plain item list, since the 7B model copied a "Dish (items)" shape into dish names), the staples and the item ratings, beside the preferences, habits, patterns and recent meals the prompt already has. A saved meal may be made as it is or inspire something close to it, and the fridge rule is unchanged.

**Suggestion pipeline:** Draft → Revise → Present, three calls, and the reply keeps its shape (text, then the ```json meal block). Code checks the draft's meal (fridge, avoid list, units: `services/fridge.py`, `models/units.py`), and the reviser (Pipeline Analyst) gets that meal, code's findings, the avoid list, dislikes and the Suggest mode (favorites: keep it familiar, a saved meal is a hint; explore: keep it new). It fixes what code found (a missing item is swapped for a fridge item that fits, or kept), answers narrow questions whose usual answer is no change (a top-priority health rule, a disliked item, a portion far off), and returns `{"changes": [...], "meal": {...}}` through Ollama structured outputs (`revision_schema` in `services/pipeline.py`: one item shape with the ingredients before the name, numeric amounts with units from the app's list on every item and ingredient, and a method; code drops a dish's own amount and unit and the method of a simple item, and turns a one-item dish named as itself back into a simple item. Offered a choice of shapes, the 7B model dropped a dish's ingredients). The review may only improve the meal: if the revised meal can't be read, or code counts more avoid-list hits in it than in the draft, or as many and more fridge misses or unknown units, the draft's meal is used. The present step then writes the text from the chosen meal alone; when it fails, code writes the menu name and description. A draft with no meal block (a fridge too small) is sent as it is. The reply is sent once the meal is chosen, not streamed. Code never removes items from a suggested menu: something the user doesn't have keeps its yellow mark so they can obtain it, and better menus come from the prompts. Progress sent via WebSocket `{type: 'progress'}`.

**After a chat** every suggestion step follows what the user typed (#161). On a Suggest press the server reads the session (`services/chat_block.py`, so every device and reload sends the same) and builds one block in chat order, oldest first: the user's typed messages, never the Suggest buttons' text (`SUGGEST_MESSAGES`, mirrored in `ChatInterface.jsx`), and the meal cards as they are now, edits included (name, dishes, items, one line each); nothing else the app wrote (chat replies, analyses, prep plans). The entries are numbered in chat order (`#1` oldest), the latest typed message is marked, and only a chat longer than `CHAT_BLOCK_CHARS` loses its oldest entries. The block's header gives the reasons: the user's words come before habits, favorites and patterns (health rules and the avoid list still hold), a later message wins over an earlier one and a message right after a menu is about it, an ask holds for every later menu as closely as the fridge allows, and a new menu differs from the ones shown. The draft and the reviser both get the block last in their message; the reviser's reply then starts with `chat_asks`, what the chat asks for now, latest first: each item lists the entries it comes from (`from`, a menu included when a message right after it is about it) before what holds now (`ask`), so a later message is read together with the earlier one it changes ("Actually simit is fine again" with "no simit") and the latest wins. It's one general list, no field per kind of request, and the review lists the asks with their entries. A fresh press sends no block, so its prompts are unchanged. Code checks nothing new: a chat can ask anything.

**Shopping persona:** suggests products you can buy, never dishes (a dish becomes its missing ingredients). Names are plain and specific, and every word names the product: "Frozen strawberries" is a different item from "Strawberries", while filler like "fresh" doesn't belong in a name. The reply is constrained by Ollama structured outputs (`SUGGESTIONS_SCHEMA` in `services/shopping.py`, sent by `chat_json` in `services/llm.py`; needs Ollama 0.5+), and the raw reply is logged when it still can't be parsed. Code then drops anything in the fridge, on the shopping list, already shown, on the avoid list or removed from the suggestions list in the last 7 days (`recently_removed`) by exact name (`same_name` in `services/fridge.py`: case, Turkish letters and plurals only), and asks once more when a whole reply was repeats. The removed items are left out by code only, so the prompt stays the same; after 7 days they may come back, and the avoid list is the permanent ban. Settings → AI settings → Removed shopping suggestions → **Bring back (N)** forgets them sooner, after an "Are you sure you want to allow N removed items back in suggestions?" prompt: `GET /shopping/suggestions/removed` counts what's left out now (the `recently_removed` rule), and `DELETE` removes the user's removed rows only, so the list on screen and the avoid list stay. Code also drops names that aren't one product ("Leafy greens (e.g. spinach)", "X or Y"; the prompt asks for alternatives as separate items next to each other) and the user's own dishes (`dish_names`: meal names and menu items made with ingredients, from all logged and favorite meals; simple items stay products). That filter is a safety net: the prompt asks for a dish's missing ingredients instead of the dish. The request message (`shopping_request`) names the reply language and, for Suggest More, the items already shown: the 7B model follows the last message better than the system prompt. Each press shows a random ~70% of the fridge (in the request) and of the user's taste hints (in the prompt, to weigh together: likes, staples, saved favorite meals with their items, habits, patterns and high-rated items; `pick_input` in `services/shopping.py`), so suggestions follow each user's own input instead of one fixed list; recent meals aren't in the prompt. Limits are in every press: health rules, the avoid list, dislikes and low-rated items. The prompt asks for about 10–15 items. Fridge items left out of a press may come back, and the dedupe drops them. The prompt test seeds the draws (`SHOPPING_SEED`), so runs compare.

**Suggestion + Analyst + Shopping** share `backend/services/knowledge.py`.

**Prompt style:** state each rule once, in the prompt that owns it, as a positive instruction with a short reason, not a growing list of bans and special cases. Anything code can verify (fridge membership, JSON shape) is checked in code, not by asking another persona to police it.

**Prompt test:** `backend/tools/prompt_check.py` runs the real suggestion pipeline (or, with `--persona shopping`, Suggest Shopping then Suggest More) for the sample users in `tools/prompt_samples.py` (en, tr, mixed, demo, sparse, vegan, and five users from the 15-fridge test: picky, diabetic, student, big_fridge, greek; `--samples all` runs them all, each in the Suggest mode its user usually presses unless `--mode` is given; `--scenario chat`, `pressed` or `all` presses after a chat instead of a fresh one: four typed messages, alone or between two earlier presses, written once as a template and filled with fixed picks from each sample's fridge (`chat_scenario`), and sent as the server's chat block (`format_chat_block` on the scenario's session rows, `chat_rows`)), or with `--persona plan` the prep planner for the menus in `PLAN_CASES` (a hard-boiled egg sandwich among them, and an omelette beside boiled eggs), against an Ollama server and scores the replies in code. For suggestions it scores the draft and the final (meal JSON, missing fridge items, renamed ones such as "White cheese (peynir)" or "Simit with tahini", units the app can't show, amounts that aren't a number with a unit, avoid-list items, dishes named after a fridge item they don't use such as a "Chia porridge" without chia, Turkish words in English replies, distinct menus; after a chat, a food it leaves out, a prep time over its limit and an earlier menu of the chat, with a liked food and a ban taken back only noted; the reviser's changes are logged as the review); for shopping it flags dishes, vague names, repeats the dedupe has to drop, and Turkish words in English replies; for plans it flags food the menu doesn't list, a dish cooked another way than its method says (fry vs boil, each plan dish held to the menu dish it names), and Turkish words in English replies, and notes each dish's step count so a plan of one step per dish shows, and the plan's switches between dishes (scheduled by the app's own code) so a plan that hops dishes every minute shows too; the bowls case is the server menu that did (#152). Run it before and after a prompt change with a `--note` (`docs/SETUPALL.md`, BONUS C): every test is logged in the git-ignored `tools/runs/` (replies, prompts sent, `history.jsonl`) and compared with the best earlier one scored by the same checks (`CHECKS`, bumped when a check changes), so keep a change only when it doesn't score worse. The pipeline yields `draft` and `review` events for it, which chat ignores. When the suggestion context gains a field, add it to the samples (a test runs every sample through the pipeline).

---

## Key Rules

- **Health rules**: injected into every LLM prompt silently. Never surface them to the user.
- **Avoid list**: hard ban. Never suggest avoided ingredients. Code matches it by exact name only (shopping dedupe, suggestion fallback): a user who bans "Peynir" and then sees "Beyaz peynir" bans that too or states a habit ("no cheese, milk included"); code doesn't guess which products an item is in.
- **Fridge constraint**: suggestions use only the inventory. Nothing is assumed: basics (salt, oil, spices) and long-life items (flour, sesame, oats…) are logged like anything else, usually in the 🫙 Pantry group. A planned Fridge quick-add button will make logging them easy. Water is a utility like electricity and gas: recipes may list it and the check skips it. The suggestion prompt doesn't mention water, so the model isn't drawn to serving it on its own. Ingredient names in the meal JSON must match the inventory as written, one item per name (a cut or form like "rolled" goes in the ingredient's `prep`), so the code check can compare them. The check matches exact names (`same_name`: case, Turkish letters and plurals only), like the avoid list and the shopping dedupe: an extra or missing word can be another product ("Cheese" isn't "White cheese", "Poached egg" isn't "Egg"), so code never guesses.
- **Date and country**: today's date and the optional Country from Settings → Profile (`user_profiles.country`, list in `utils/countries.js` with ISO 3166-1 alpha-2 codes) go into the shopping and suggestion prompts (`format_today`), so "in season" means something. The selector lists "Germany (DE)" and shows only "DE" once chosen; the saved value is the name. The profile text the analysts read leaves the country out.
- **Context length**: every Ollama call sends the same `num_ctx` (`OLLAMA_NUM_CTX`, 8192 by default, `_options` in `services/llm.py`). Chat history is about 6000 tokens and Ollama's own 4096 drops the oldest messages silently; one value for all calls keeps Ollama from reloading the model. The KV cache fits a 6 GB GPU (`docs/SETUPALL.md`, Step 1).
- **CORS**: configurable via `CORS_ORIGINS` env var (comma-separated).
- **Auth**: a name and a PIN, set with `manage.py add-user` or `set-pin` (both ask for the PIN, hidden, when `--pin` is left out); tokens live in memory, so a restart logs everyone out. PINs are stored as salted scrypt hashes (`scrypt$n$r$p$salt$hash`, OWASP-aligned cost in `SCRYPT_*` in `auth.py`), checked off the event loop and with `hmac.compare_digest`; an unknown name is checked against a dummy hash, so timing doesn't tell names apart. Plain SHA-256 hashes from before scrypt still log in, and that login re-hashes them, like any hash at an older cost. New or changed PINs take 6-10 digits, digits only since the login screen opens the number pad (`pin_problem`); PINs set before the rule still log in until `set-pin` replaces them, and login takes names up to 100 characters and PINs up to 64 (422 beyond). Failed logins are counted in memory per name on each client IP, one counter per pair, so typos on a shared device don't lock other users there and nobody can lock a user out of their own device: repeated failures get 429 with `Retry-After`, the wait growing with each further one (exponential backoff), and the PIN isn't checked while locked; each attempt counts before the check, so parallel requests can't slip past, a success clears the count, and a quiet spell forgets it (the `LOGIN_*` limits in `auth.py`). The login screen shows the wait (CORS exposes `Retry-After`). Tests hash at a tiny cost (`conftest.py`) unless marked `real_scrypt`.
- **Demo user**: only created when `DEMO_USER=true` (empty PIN), and the empty PIN logs in only while it's on, so a leftover demo account is locked once it's off. A newly created demo account gets a starter fridge (`DEMO_FRIDGE` in `models/ingredient.py`, basics included). Never enable it on a reachable instance.
- **Language**: the UI is English only; the setting changes AI replies. User data is often Turkish and pulls a 7B model toward Turkish, so every user-facing prompt ends with a `FINAL REMINDER` restating the language directive. Code-built text in replies (e.g. prep plan labels) follows the same setting, and so do units.
- **Theme**: Settings → Theme (orange default, then green, teal, blue, purple: hues spread around the wheel, each nudged warm, all WCAG AA) changes only `--accent`, `--accent2`, `--secondary` / `--secondary-soft`, the assistant bubble `--bubble` and the prep plan's dish colors `--dish-1` … `--dish-4` (`index.css`, `:root[data-theme=…]`). Use those variables or `secondaryColor`, never a hard-coded accent hex. `--dish-1` is the accent and the other three are hues spread around the wheel from it at the accent's lightness (the secondaries fail AA on the bubble and share the accent's hue), kept away from the delete red and the missing-item yellow, each AA on its bubble (a theme test checks the contrast). A plan in the new format (`⏱ Plan (` heading, `utils/prepPlan.js`) gets a thin bar per dish down the left of its lines, ↳ lines included, and the dish name on a time line in the same color; dishes take colors in order of first appearance and a fifth reuses the first. Older plans and lyric fallbacks render as plain Markdown, and nothing is added to the plan text. Semantic colors never follow the theme: red (`colors.danger*`) means delete/remove, health-rule priorities are a traffic light (red top priority, yellow care a lot, green don't really care), plus expiry warnings and stars. Saved as the `theme` preference and cached in `localStorage` (`utils/theme.js`).
- **App settings vs food preferences**: settings stored as preferences (`SETTING_KEYS` in `services/context.py`: language, theme, weekly-summary toggle) are kept out of prompts.
- **Line endings**: `.gitattributes` normalizes to LF in repo, CRLF on Windows checkout.

---

## Shared Components

**MealEditor** (`frontend/src/components/MealEditor.jsx`) — used everywhere (chat, favorites, meal history, "Today I ate"). Key props: `menuMode`, `onFavorite(currentMeal) => favoriteId` with `onUnfavorite(favoriteId)`, `extraActions(buildCurrentMeal) => ReactNode`. The function form of `extraActions` gives callers access to live editor state. `checkFridge` underlines ingredients that aren't in the fridge (via `POST /ingredients/check`, same matching as the pipeline) in yellow; tapping one marks it as obtained for this meal (green, stored as `meal.obtained`). A tap on a dish's name marks all of its missing items (its name included) as obtained, or unmarks them all, without opening the dish; a tap beside the name opens it, and only a name's text marks. `onMissingChange(names)` reports what's still missing and not obtained; `onChange(meal)` reports live state. On in chat meal details (marks are saved with the card and carry into "Today I ate", not back) and in "Today I ate", where Confirm waits until nothing is missing. The header is a ☆ left of the meal name (with `onFavorite`), the name, and the prep time in "min". Favorite names are unique per user (exact, any case): `POST /favorites` and a rename through `PUT /favorites/{id}` get 409 when another favorite has the name, while favorites that shared a name before the rule keep theirs. The star is a gold ⭐ when a favorite has the meal's name as typed and the same food (`menuKey` in `utils/ingredients.js`: items, dish ingredients, amounts and units in any order, names in any case, units in English; marks, times, methods and prep words don't count), so meals saved earlier show it too; the favorites are loaded when the editor opens. A tap on ☆ adds the meal and a tap on ⭐ removes that favorite. When another favorite has the name with other food, ☆ saves nothing and a note asks for a new name or an edit of that favorite in Favorites, whose own editor keeps a refused rename open with a note. Chat cards show the name and prep time, without the meal's id. "Today I ate" Save stores the editor's meal with its chat card (`ate_draft` on the card's message, saved through `PUT /sessions/{id}/messages/{message_id}`, which changes only the fields it is sent) and closes the panel, so the user's other devices get it. The panel opens from the card's saved version if there is one, else from the card, and each card keeps its own. Close drops unsaved edits, Back from rating returns to the edited menu, the last Save wins, and a push never resets an open panel. The buttons are Close, Save, Confirm (Confirm last); the rating step has Back, Skip (logs without ratings) and Confirm. Logging the meal clears the card's saved version and unselects the card, on every device. Chat cards and Favorites rows show readiness on their icon (`ReadinessIcon` + `hooks/useMealReadiness.js`: yellow = missing, green = ready). Favorites are templates: their editor shows the yellow underline only (`canMarkObtained={false}`). The plain Save button only appears when the caller passes `onSave`. Callers must pass a stable `meal` object: a new object resets the editor's edits.

**ConfirmPrompt** (`frontend/src/components/ConfirmPrompt.jsx`) — the inline "Are you sure?" box: the question, Cancel, then the action (red with `danger`, for a delete; the theme color otherwise). Used before both Delete all buttons (shopping list, shopping suggestions) and Settings' Bring back. A single delete (× on a row) doesn't ask.

**Units** — source of truth: `backend/models/units.py` (`UNIT_PAIRS`: each English unit paired 1-1 with its Turkish match, plus `UNIT_ALIASES` like "gr" → g), mirrored in `frontend/src/utils/ingredients.js`. Edit both locations. Spoons and glasses have one fixed size in both languages (`UNIT_ML`: tsp 5 ml … glass / su bardağı 200 ml), stated in the suggestion prompt and shown only in the editor's open unit list, so an amount means the same in either language; "cup" is deliberately not a unit (a US cup is 240 ml). Units follow the AI language (English list by default, Turkish in Turkish mode): the suggestion prompt lists them, and stored meals keep their units as written while known ones are shown in the current language (`localizeUnit`; the prep-plan input does the same). The frontend reads the language from `utils/language.js` via `useLanguage()`, set at login and by the Settings toggle.

**Unit memory** (`frontend/src/utils/ingredients.js`) — `unitsFor(language)`, `resolveUnit(name)` (localStorage memory → smart keyword default from Turkish or English names → pcs / adet, shown in the current language), `rememberUnit(name, unit)`.

**Ingredient groups** — source of truth: `backend/models/ingredient.py` (INGREDIENT_GROUPS), mirrored in `IngredientPanel.jsx`. Edit both locations to change groups. A new item (Fridge add, bulk add, bought from the shopping list) gets the group picked in the add panel ("Auto" picks none), else the user's own pick for the name (`ingredient_group_memory`), else the built-in food list's, else Other (`services/ingredient_groups.py`). Names match exactly (`same_name`), so "Free-range eggs" goes to Other until the user moves it once. Memory records every name added to the Fridge with its group (a planned quick-add lists what the user had before), and only rows marked `picked` count as the user's choice: a group picked in the add panel, or given in an edit when code wouldn't give the name that group (a move, or a renamed item keeping its group), never a group code chose. A new pick unmarks earlier picks for the same name, and a group code chose never overwrites a pick.

**Food list** (`backend/data/ingredient_catalog.json`) — about 600 common breakfast and home-kitchen foods by group, each `{"en": [...], "tr": [...]}`: the first name in each language is the display name (a planned Fridge quick-add can show it), the others are spellings of the same food. Written for the project and edited by hand. A name that could be two groups ("Pepper": spice or produce) stays off it, so its item goes to Other. Tests check that no name is on it twice, every food has both languages and `DEMO_FRIDGE` matches it. A one-time pass at start (`PRAGMA user_version` 1) marked old memory rows as picks unless they say Other (the old code saved the Other default on every add, so those stay plain names) and moved Other items the list knows.

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
│   ├── auth.py                      ← scrypt PIN hashing, login rate limit + in-memory bearer tokens
│   ├── manage.py                    ← admin CLI (add/list/delete users, set-pin)
│   ├── db_helpers.py                ← reusable DB query helpers
│   ├── data/
│   │   └── ingredient_catalog.json  ← built-in food list: ~600 foods by group, English + Turkish names
│   ├── tools/
│   │   ├── prompt_check.py          ← prompt test: real pipeline vs Ollama, replies scored in code
│   │   └── prompt_samples.py        ← sample users (English and Turkish fridges) for it
│   ├── routers/
│   │   ├── chat.py                  ← WebSocket /chat
│   │   ├── meals.py                 ← /meals history
│   │   ├── ingredients.py           ← /ingredients CRUD + groups
│   │   ├── favorites.py             ← /favorites (saved meals, unique names per user)
│   │   ├── favorite_ingredients.py  ← /favorite-ingredients (staples)
│   │   ├── shopping.py              ← /shopping list (DELETE / empties it) + /shopping/suggestions (Fridge tab list, per user; removed count, bring back)
│   │   ├── analyst.py               ← /analyst/analyze
│   │   ├── scheduler.py             ← /scheduler/plan (steps per dish, hands-on blocks kept whole, finishing together)
│   │   ├── kitchen.py               ← /kitchen appliance config
│   │   ├── sessions.py              ← /sessions
│   │   ├── profile.py               ← /profile + supplements
│   │   ├── ratings.py               ← /ratings
│   │   ├── health_rules.py          ← /health-rules
│   │   ├── preferences.py           ← /preferences + habits
│   │   └── auth.py                  ← /auth/login (429 + Retry-After after repeated failures)
│   ├── services/
│   │   ├── personas/                ← one file per LLM persona
│   │   ├── pipeline.py              ← 3-step suggestion pipeline
│   │   ├── context.py               ← shared context loaders for prompts
│   │   ├── knowledge.py             ← shared food knowledge
│   │   ├── insights.py              ← behavioral pattern extraction
│   │   ├── fridge.py                ← exact name matching (same_name): fridge check, avoid hits
│   │   ├── ingredient_groups.py     ← a new item's group: the user's pick, then the food list, then Other
│   │   ├── shopping.py              ← shopping reply schema, parser + dedupe (+ items removed in the last 7 days)
│   │   ├── suggestion.py            ← stream_response + persona re-exports
│   │   ├── chat_sync.py             ← open chat sockets per user: session_updated + small notices
│   │   ├── chat_block.py            ← the chat a Suggest press reads: typed messages + meal cards, latest marked
│   │   └── llm.py                   ← Ollama streaming + lyric fallback
│   └── models/
│       ├── ingredient.py            ← INGREDIENT_GROUPS (source of truth)
│       ├── kitchen.py               ← KITCHEN_APPLIANCES (source of truth; `hot`: its food cools while it waits)
│       ├── units.py                 ← UNIT_PAIRS English ↔ Turkish (source of truth)
│       └── meal.py                  ← MealLog, Meal (includes menu_items)
└── frontend/src/
    ├── App.jsx                      ← tab nav (Chat, Fridge, Preferences, Settings)
    ├── utils/ingredients.js         ← ingredient helpers, units per language + unit memory
    ├── utils/language.js            ← AI language store (cached per device, like the theme)
    ├── utils/countries.js           ← Country list (name + ISO code) for Settings → Profile
    ├── utils/prepPlan.js            ← reads new-format prep plans: the dish and dish color of each line
    ├── styles/common.js             ← shared styles
    ├── services/api.js              ← all REST + WebSocket calls
    ├── hooks/useVoice.js            ← Web Speech API
    ├── hooks/useLanguage.js         ← current AI language, re-renders on change
    ├── hooks/useMealReadiness.js    ← fridge readiness for a meal (card + favorites badge)
    ├── hooks/useSyncNotice.js       ← app-wide sync notices from the chat socket
    └── components/
        ├── ChatInterface.jsx        ← main chat UI
        ├── MealBlock.jsx            ← inline meal block in chat
        ├── MealEditor.jsx           ← shared meal editor (used everywhere)
        ├── PrepPlanText.jsx         ← prep plan message with a colored bar per dish
        ├── DecidePanel.jsx          ← "Today I ate" flow
        ├── ConfirmPrompt.jsx        ← shared "Are you sure?" box (Delete all, Bring back)
        ├── SuggestButton.jsx        ← suggest button + mode picker
        ├── IngredientPanel.jsx      ← Fridge tab
        ├── PreferencesPanel.jsx     ← favorites, dislikes, habits, avoid
        ├── SettingsPanel.jsx        ← profile, supplements, health rules, history, bring back removed suggestions
        ├── FavoritesPanel.jsx       ← saved meals panel
        ├── WeeklySummary.jsx        ← weekly meals + nutrition summary
        └── KitchenSettings.jsx      ← appliance toggle grid
```

---

## Glossary

**Makespan** — total wall-clock time from first task to last in a cooking plan.

**Warm prior** — stated habit treated as a starting assumption, updated by observed behaviour.

**Favorites / Explore modes** — favorites optimises for familiar meals; explore finds novel meals adjacent to the user's taste profile.
