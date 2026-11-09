# Model Tests

Local models to compare against the current `qwen2.5:7b` (Q4_K_M) with the prompt test
(`backend/tools/prompt_check.py`, see `SETUPALL.md`, BONUS C). Found on 2026-11-09 with
LLMFIT and an online search.

## Server

- GPU: RTX 2060 laptop, 6 GB VRAM. CPU: i7-10750H (6 cores). RAM: 16 GB.
- Ollama 0.40.15, `OLLAMA_FLASH_ATTENTION=1`, `OLLAMA_KV_CACHE_TYPE=q8_0`, `OLLAMA_NUM_PARALLEL=1`.
- The app sends `num_ctx` 8192 on every call. `qwen2.5:7b` runs there 100% on the GPU at
  about 45 tokens/s.
- Models are stored on C: (126 GB free).

## How to test a model

1. On the server, download it: `ollama pull <tag>` (`ollama list` shows what's there).
2. On the development PC, from `backend/` (where `backend/.env` already has `OLLAMA_BASE_URL`):

   ```powershell
   python -m tools.model_battery qwen2.5:7b
   python -m tools.model_battery qwen3:8b --think off
   python -m tools.model_battery qwen3:8b --think on
   ```

   `tools/model_battery.py` loads the model at the app's 8192 context and prints how much of
   it is on the GPU. Then it runs the same set of prompt tests for every model (`SUITES`):
   - Suggest on all 12 samples, first fresh and then after a chat
   - the reviser cases and the prep plan cases
   - shopping for en, tr, vegan and diabetic
   - chat replies for en, tr and student

   Each test is saved in `tools/runs/` and `history.jsonl` with the model and the think
   setting. A single test still runs with `python -m tools.prompt_check ... --model <tag>
   --think on|off`. The app's servers aren't needed: the tests call Ollama directly.
3. Run `qwen2.5:7b` first as the baseline.
4. Run one test at a time from one PC. Tests share the server's GPU, and the timings only
   compare when nothing else is using it.

Ollama keeps only one of these models in 6 GB of VRAM at a time. A test of another model
unloads `qwen2.5:7b`, and the app's next call loads it again (a few seconds).

**Thinking models** (marked 🧠) can think before they answer. Ollama's `think` field turns
this on or off, and the app sends none by default, so each model does its own default
(Qwen3 and Qwen3.5 think). `OLLAMA_THINK=true` or `false` in `backend/.env` sends it with
every call; models that can't think refuse it, so leave it unset for them. Test each 🧠
model twice, with `--think off` and `--think on`.

Thinking costs time: often hundreds to a few thousand tokens before every answer (about
45 tokens/s here), on each of a suggestion's three calls, and the chat shows nothing while
the model thinks.

## Plan

1. **Code scores.** Run the test set for every model in the tables below, and twice for
   each 🧠 model (think off and on). Record the clean share per persona, errors and
   timeouts, average seconds per press, and the GPU share in the Result column.
2. **Blind comparison page.** A page that reads two runs and shows each sample's replies
   side by side as "A" and "B" (the menu, reply text, prep plan or chat reply, with the
   code's flags and seconds), the models hidden. You vote **A**, **B** or **both equally
   good**, and the page shows which model was which and the tally at the end.
   It needs the runs as data: `save_log` writes only Markdown now, so add a JSON file per
   run next to the `.md` (records with replies and scores, plus the header).
3. **Claude rates the breakfasts.** Claude reads the same pairs blind and votes too, with a
   short reason for each, judging breakfast quality: does it make a real, balanced
   breakfast from the fridge, are portions sensible, is the text natural English or
   Turkish, does it follow the chat.
4. **Compare the judgements.** At the end, put your votes next to Claude's per sample and
   per model, and see where they differ.
5. **Choose.** Weigh the code scores, both sets of votes and speed. If the best is a
   🧠 model, decide think on or off, and then finish the app side (for example, the chat
   showing that the model is thinking).

## First results

- **qwen2.5:7b baseline** (2026-11-09, server, Suggest fresh, 1 press per sample): final
  10/12 clean, 21–47 s per press (35 s on average). Demo named a dish after an item it
  doesn't use ("Eggs with Red Pepper Flakes"), and bare served "Hot Water for Tea"
  instead of sending a note. The other tests weren't finished; run the full set again.
- With one press per sample, almost every reply is clean, so the code scores barely tell
  the models apart. Use `--runs 2` or more for the finalists, and let the blind votes decide
  the rest.

## Models

Fit is estimated for an 8192-token context: download size plus KV cache. LLMFIT is the
tool's verdict, run with an 8192-token context cap.

### 1. Fit on the GPU

| Model | Tag | Download | Fit | LLMFIT | Notes | Result |
|---|---|---|---|---|---|---|
| Qwen3 4B Instruct 2507 | `qwen3:4b-instruct-2507-q8_0` | 4.3 GB | 100% GPU | Perfect, ~46 tok/s | No thinking. `-q4_K_M` is 2.5 GB | |
| Gemma 3 4B | `gemma3:4b` | 3.4 GB | 100% GPU | Perfect (base model) | Strong across many languages | |
| Qwen3.5 4B 🧠 | `qwen3.5:4b` | 3.3–4.0 GB | 100% GPU | Perfect, ~40 tok/s | 2026, top 6 GB pick in several guides | |
| Gemma 4 E2B | `gemma4:e2b-it-q4_K_M` | 4.6 GB | 100% GPU | Perfect, ~48 tok/s | 2026 | |

### 2. About 8B, at the edge of 6 GB

| Model | Tag | Download | Fit | LLMFIT | Notes | Result |
|---|---|---|---|---|---|---|
| Llama 3.1 8B | `llama3.1:8b` | 4.9 GB | Probably 100% GPU | Marginal (90%), ~46 tok/s | 2024. Turkish isn't one of its listed languages | |
| Aya Expanse 8B | `aya-expanse:8b` | 5.1 GB | Edge, maybe a small CPU share | not listed | Cohere, 23 languages including Turkish. Context is 8K at most, exactly the app's 8192 | |
| Granite 4.2 8B 🧠 | `granite4.2:8b` | 5.3 GB | Edge, maybe a small CPU share | not listed (4.0 only) | IBM, made for JSON output | |
| Qwen3 8B 🧠 | `qwen3:8b` | 5.2 GB | Edge, maybe a small CPU share | Marginal (96%), ~45 tok/s | Closest upgrade from qwen2.5:7b | |

### 3. CPU share (slower)

| Model | Tag | Download | Fit | LLMFIT | Notes | Result |
|---|---|---|---|---|---|---|
| Gemma 4 E4B 🧠 | `gemma4:e4b-it-qat` | 6.1 GB | CPU share | Marginal (94%), ~46 tok/s | Praised for instruction following | |
| Ministral 3 8B | `ministral-3:8b` | 6.0 GB | CPU share | not listed (2410 only) | Mistral, Dec 2025, reliable JSON. `:3b` (3.0 GB) fits the GPU | |
| Qwen3.5 9B 🧠 | `qwen3.5:9b` | 6.6 GB | CPU share | Marginal (96%) | Quality ceiling | |

Each call has a 120-second timeout (`services/llm.py`). A slow model on CPU share, or one
that thinks, can run past it.

## Left out

- `gpt-oss:20b`: about 14 GB, more than the server's free RAM.
- `granite4`, `phi4-mini`: weak in Turkish.
- LLMFIT's top picks: vLLM-only builds (AWQ/GPTQ) and large MoE models that expect their
  experts in RAM.
- Turkish fine-tunes from the community: to discuss later.
