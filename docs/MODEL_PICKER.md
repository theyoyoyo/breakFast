# Model picker

A small page for the server's admin: choose which Ollama model each task and each reply language uses, and whether it thinks. It is a tool beside the app, not part of it. The app never serves it.

## Run it

On the server, from `backend/`:

```powershell
python -m tools.model_picker
```

Open <http://127.0.0.1:8765>. `--port` changes the port and `--url` the Ollama address (default `OLLAMA_BASE_URL`). It listens on `127.0.0.1` only, with no option for another address: open it on the server itself, or through a Tailscale tunnel to that port.

## What it sets

One dropdown per task (chat, suggestion, review, analyst, shopping, plan, weekly) and per reply language (en, tr), filled from the models Ollama has installed. "default (.env: …)" leaves a key to `.env`. A think control (default / on / off) shows only for models that report they can think.

Save writes `backend/model_settings.json` (git-ignored). The backend re-reads it when the file changes, so **no restart is needed**: a call already running keeps its model, and the next call uses the new one.

## How a call chooses

1. **Model:** the reply language's model, then the task's, then `OLLAMA_MODEL`. A language model therefore overrides every per-task model for that language's users.
2. **Think:** that model's own setting, then the global `OLLAMA_THINK`, then off for the default model only. Any other model with nothing set sends no think field.
3. **Precedence:** the picker's file wins over `.env`, and `.env` over the defaults. A key set in the file replaces that key's `.env` entry whole, model and think together; a file entry without think falls back to `OLLAMA_THINK`, not to `.env`'s `OLLAMA_THINK_<KEY>`, which was meant for a different model.

A missing file means no overrides. A broken or invalid file keeps the last good settings and logs a warning, so a bad edit never reaches a request.

## Things to know

- Two models that don't fit the GPU together reload at every switch, so each press waits. Keep the set small, and change models when the house is quiet.
- A global `OLLAMA_THINK` reaches every route without its own think value. If such a model can't think, Ollama refuses the call and the user gets a lyric, so leave `OLLAMA_THINK` unset unless every model can take it.
- The picker blocks think only on its own entries, and only for models that can think.
- Save refuses a model Ollama doesn't list, with a fixed message. A saved model Ollama no longer lists can be kept as saved, so the other keys can still be saved. If Ollama is down the page opens with a note and Save returns 503.

## Safety

- Binds to `127.0.0.1` only; the Host header is checked on every request and Origin on writes (403 otherwise), so another site in the browser can't change the settings.
- Save takes JSON only, at most 16 KB, and answers with fixed messages that never echo the input.
- Model names are escaped on the page, which has a strict content security policy and no external assets.
- The file is written atomically (temp file, then replace).

## Without the page

The same settings work in `.env`: `OLLAMA_MODEL_<TASK>` and `OLLAMA_THINK_<TASK>` per task, `OLLAMA_MODEL_EN` / `OLLAMA_MODEL_TR` per language (see `.env.example`). The step-by-step admin guide is in `docs/SETUPALL.md`, and comparing models before choosing is in `docs/MODEL_TESTS.md`.
