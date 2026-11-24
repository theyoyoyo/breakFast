# Configuration

All backend settings are environment variables. Copy `.env.example` to `.env` and change what you need; every variable is documented inside [`.env.example`](../.env.example).

| Variable | Default | Purpose |
|---|---|---|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server |
| `OLLAMA_MODEL` | `gemma4:e4b-it-qat` | Model for every call without its own |
| `OLLAMA_MODEL_<KEY>` | none | A model for one task (`CHAT`, `SUGGESTION`, `REVIEW`, `ANALYST`, `SHOPPING`, `PLAN`, `WEEKLY`) or reply language (`EN`, `TR`) |
| `OLLAMA_THINK`, `OLLAMA_THINK_<KEY>` | none | Ollama's think setting, `true` or `false`, for models that can think |
| `OLLAMA_NUM_CTX` | `8192` | Context length sent with every call |
| `OLLAMA_TIMEOUT` | `150` | Seconds a call may wait for Ollama |
| `DATABASE_PATH` | `./breakFAST.db` | SQLite file, relative to `backend/` |
| `CORS_ORIGINS` | `*` | Comma-separated allowed origins |
| `SERVE_FRONTEND` | `false` | Serve `frontend/dist` from FastAPI |
| `API_DOCS` | `false` | Serve `/docs`, `/redoc` and `/openapi.json` |
| `DEMO_USER` | `false` | Create a `demo` user with an empty PIN and a starter fridge |

## Choosing models

`OLLAMA_MODEL` is the default for every call. A task or a reply language can have its own model with `OLLAMA_MODEL_<KEY>` (and its own think setting with `OLLAMA_THINK_<KEY>`). A call uses its language's model, else its task's, else `OLLAMA_MODEL`.

On the server, `python -m tools.model_picker` (from `backend/`) picks the models on a small local page and writes `backend/model_settings.json`, which is read on every call, so no restart is needed. See [Model picker](MODEL_PICKER.md) and [Choosing models](SETUPALL.md#choosing-models-admin-optional) in the setup guide.

## Demo user

`DEMO_USER=true` creates a `demo` account with an empty PIN and a small starter fridge. Keep it off on any instance other people can reach.

---

Back to the [README](../README.md).
