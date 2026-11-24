# Architecture

How break FAST is built: the personas behind the AI features, the engineering choices that keep a small local model reliable, and where things live in the repository. The [README](../README.md) has the overview and the diagrams.

## Personas

For every request the backend loads the user's context (fridge, recent meals, profile, supplements, health rules, avoid list, appliances, language) and hands it to one of seven personas. Each has its own prompt in `backend/services/personas/`.

| Persona | Job | File |
|---|---|---|
| Chat | A casual breakfast buddy that helps work out what you want, one question at a time | `chat.py` |
| Suggestion | Drafts the menu from the fridge (favorites and explore modes) and writes the short reply | `dietitian.py` |
| Reviser | Fixes what code found in the draft and answers a few narrow questions about the menu | `pipeline_analyst.py` |
| Nutrition analyst | Estimates a meal's nutrition, cached per meal | `analyst.py` |
| Weekly analyst | Reviews seven days of meals: four scores, a summary and the nutrients lacking or more than enough | `weekly_analyst.py` |
| Shopping | Suggests specific products to buy, never dishes | `shopping.py` |
| Prep planner | Splits each dish into steps and estimates minutes and appliances | `scheduler.py` |

## Engineering highlights

- **Structured outputs.** The draft, the review, the weekly analysis and the shopping suggestions use Ollama's JSON schema mode, so the reply has the right shape. The reviser's ingredient names are limited to the fridge, so a swap can only bring in what you have.
- **Code checks, not prompt policing.** Anything code can verify (fridge membership, the avoid list, units, JSON shape) is checked in code with exact name matching. Prompts state each rule once, with a short reason.
- **The review may only improve the meal.** The revised menu is used only if it is no worse than the draft by code's count of fridge misses, avoid-list hits and unknown units.
- **Deterministic scheduling.** The model estimates; tested Python code does the timing.
- **A model per task.** A task or reply language can have its own model, and the model picker changes them without a restart.
- **Prompt test harness.** `backend/tools/prompt_check.py` runs the real prompts against a real model for a set of sample users and scores every reply in code. It covers suggestions, the review, shopping suggestions, chat replies and prep plans. Every run is logged and compared with the best earlier run, so a prompt change that scores worse is caught. The same harness compares candidate models.
- **Stop that really stops.** Stop cancels the request on the server and closes the model call, so Ollama stops generating. One chat request per user runs at a time, across all their devices.
- **Live sync.** Each user's open WebSocket connections get a small push when something changes, so other devices reload only what changed. No polling.
- **Database migrations.** Numbered steps tracked with SQLite's `user_version`, each applied in one transaction. A database with data is backed up and integrity-checked before any step runs.
- **Tests and CI.** pytest (with Ollama faked), Vitest, ruff and ESLint run on GitHub Actions for every pull request.

## Project structure

```text
breakFast/
├── backend/
│   ├── main.py, config.py    FastAPI app and settings
│   ├── database.py           SQLite schema and migrations
│   ├── auth.py, manage.py    PIN login, sessions and the admin CLI
│   ├── routers/              one module per API area (chat WebSocket, meals, fridge, ...)
│   ├── services/
│   │   ├── personas/         one file per LLM persona
│   │   ├── pipeline.py       draft → review → present
│   │   ├── prep_plan.py      prep plan scheduling
│   │   └── llm.py            Ollama calls
│   ├── models/               request models, units, groups, appliances, limits
│   ├── data/                 built-in food list
│   ├── tools/                prompt test, model tests, model picker
│   └── tests/                pytest suite
├── frontend/
│   ├── src/                  React app (components, hooks, services/api.js)
│   ├── brand/                logo master files
│   └── public/               PWA icons and favicons
├── docs/                     setup guide, architecture, configuration, model notes, screenshots
├── .github/workflows/        CI
├── CLAUDE.md                 product decisions and conventions
└── setup.bat, start.bat, start-server.bat
```

---

Back to the [README](../README.md).
