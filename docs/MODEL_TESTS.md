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
   - Suggest on all 12 samples fresh, and on 10 after a chat (bare's fridge is too small, and en and tr
     cover mixed's)
   - the reviser cases and the prep plan cases
   - shopping for en, tr, vegan and diabetic
   - chat replies for en, tr and student

   Each test is saved in `tools/runs/` and `history.jsonl` with the model and the think
   setting, and compared only with earlier tests of the same model and think setting. A
   single test still runs with `python -m tools.prompt_check ... --model <tag> --think
   on|off`. The app's servers aren't needed: the tests call Ollama directly.

   The battery also writes the data the comparison page reads (`--data`), in the git-ignored
   `tools/runs/models/`: `inputs/<test>.json`, what every model gets for each sample (the same
   for every model), and `<model>/<test>.json`, one folder per model and think setting, with
   each sample's replies, the code's flags, seconds and errors, the prompt version and the GPU
   share. A rerun replaces that model's outputs for the samples it ran and keeps the others, so
   one sample can be run again on its own; each output names the prompt version it ran on.
3. Run `qwen2.5:7b` first as the baseline.
4. Run one test at a time from one PC. Tests share the server's GPU, and the timings only
   compare when nothing else is using it.
5. Build the comparison page against the baseline:

   ```powershell
   python -m tools.compare_runs qwen3.5:4b --think off
   ```

   It writes `tools/runs/models/compare_<baseline>__vs__<model>.html`, one page to open in a
   browser:
   - **Blind A/B:** each sample's input (the fridge, the chat, the draft or menu) above the
     two models' replies, as A and B in an order seeded by the pair, so a rebuild keeps it.
     Votes are A, B or both equally good, with a note, kept in the browser; **Download
     votes** saves them as `<pair>__user.json`. Save it in `tools/runs/models/votes/` so a
     rebuild shows it.
   - **Reveal** names the models on every pair and shows the tally, yours and Claude's.
   - **All models**, after Reveal: a chart per test of every model tried (clean share,
     seconds, GPU share; a grey bar ran on another prompt version than the baseline), and a
     table of samples by models.

   `votes/<pair>__blind.json` has the same pairs without the models or seconds, for Claude's
   blind votes (`votes/<pair>__claude.json`, `{"votes": {pair id: {"vote": "A"|"B"|"tie",
   "reason": ...}}}`); `votes/<pair>__key.json` says which model each pair's A is.

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
2. **Blind comparison page** (`tools/compare_runs.py`, step 5 above). It shows each
   sample's replies side by side as "A" and "B" (the menu, reply text, prep plan or chat
   reply, with the code's flags and seconds), the models hidden. You vote **A**, **B** or
   **both equally good**, and the page shows which model was which and the tally at the end.
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

### Battery, 2026-11-09 (prompt 80fe68c, one press per sample)

Clean replies per test, average seconds per sample in brackets:

| Model | Suggest | After a chat | Review | Plan | Shopping | Chat | GPU |
|---|---|---|---|---|---|---|---|
| `qwen2.5:7b` | 10/12 (31) | 9/11 (35) | 4/5 (15) | 6/8 (12) | 0/4 (25) | 1/3 (8) | 100%, 4.8 GB |
| `qwen3.5:4b` think off | 10/12 (29) | 8/11 (33) | 5/5 (13) | 6/8 (10) | 1/4 (20) | 1/3 (10) | 100%, 3.2 GB |

**Claude's blind votes** on the 43 pairs: `qwen3.5:4b` 27, `qwen2.5:7b` 14, equal 2.

| Test | qwen2.5:7b | qwen3.5:4b | Equal |
|---|---|---|---|
| Suggest | 3 | 9 | 0 |
| After a chat | 4 | 6 | 1 |
| Review | 3 | 2 | 0 |
| Plan | 4 | 4 | 0 |
| Shopping | 0 | 3 | 1 |
| Chat | 0 | 3 | 0 |

- **qwen3.5:4b stronger:**
  - sent bare's note instead of a menu;
  - made a good Greek plate where qwen2.5 made a "hummus soup" with nori;
  - kept the egg-white intent in the review's omelette;
  - wrote more coherent Turkish menus and chat replies;
  - kept its shopping lists from repeating the fridge.
- **qwen3.5:4b weaker:**
  - set chia pudding for 45–60 minutes in two plans (49 and 62 minutes in all);
  - left a swap unmarked in the pancakes;
  - garbled the mixed sample's dish names;
  - cooked on a buttered pan after a butter ban;
  - once put white bread in a diabetic user's menu.
- **Both:** odd prep words ("eggs: chopped"), filler methods on simple items, and occasional food the chat persona shouldn't propose.
- **Blindness:** Claude saw the per-test clean counts before voting, so a pair where only one reply had a flag could hint at its model. The votes judge the replies themselves.
- **Your votes** (prompt a5c7028, against `qwen2.5:7b`):
  - `gemma3:4b`: 14–14, equal 15. The two tr chat pairs still need a vote on their Turkish replies.
  - `gemma4:e2b-it-q4_K_M` think on: 9–9, equal 24. Every Turkish sample went to gemma4 (5–0: suggest, after a chat, plan, shopping, chat), and shopping 2–0. Suggest went 3–2 to qwen2.5, and after a chat 3–2.
  - `gemma4:e4b-it-qat` think off: 17–3, equal 22. Suggest 6–0, plan 6–0, every Turkish sample 5–0, after a chat 2–1, review 1–0, shopping 1–1, chat 1–1.

### Every model, 2026-11-09 and 10 (prompt a5c7028, one press per sample)

Clean replies per test, average seconds per sample in brackets, and the model's share on the 6 GB GPU. A reply that hit the 120 s timeout counts as an error. Thinking on made `qwen3.5:4b`, `qwen3.5:9b` and `granite4.2:8b` time out on almost every JSON reply, and the plans they did finish took minutes. The data is archived in `tools/runs/models-archive-a5c7028/`, since the fuller samples (#188) give a new prompt version.

| Model | Suggest | After a chat | Review | Plan | Shopping | Chat | GPU |
|---|---|---|---|---|---|---|---|
| `gemma4:e4b-it-qat` think off | 12/12 (37) | 7/10 (33) | 5/5 (14) | 6/8 (12) | 0/4 (21) | 3/3 (9) | 100% |
| `gemma4:e4b-it-qat` think on | 12/12 (93) | 9/10 (100) | 5/5 (34) | 6/8 (39) | 0/4 (78) | 3/3 (44) | 100% |
| `gemma4:e2b-it-q4_K_M` think on | 11/12 (40) | 10/10 (45) | 5/5 (15) | 5/8 (12) | 0/4 (35) | 2/3 (23) | 100% |
| `gemma4:e2b-it-q4_K_M` think off | 10/12 (14) | 9/10 (15) | 5/5 (5) | 4/8 (4) | 0/4 (10) | 1/3 (5) | 100% |
| `gemma3:4b` | 9/12 (23) | 9/10 (26) | 5/5 (12) | 6/8 (8) | 0/4 (18) | 3/3 (7) | 100% |
| `qwen2.5:7b` | 10/12 (31) | 9/10 (34) | 4/5 (15) | 6/8 (12) | 0/4 (25) | 1/3 (8) | 100% |
| `qwen3.5:4b` think off | 10/12 (29) | 8/10 (33) | 5/5 (13) | 6/8 (10) | 1/4 (20) | 1/3 (9) | 100% |
| `qwen3.5:4b` think on | 1/12, 11 timeouts | 1/10, 9 timeouts | 0/5 | 5/8 (169) | 0/4, 4 timeouts | 3/3 (333) | 100% |
| `qwen3:4b-instruct-2507-q8_0` | 10/12 (42) | 3/10 (44) | 5/5 (20) | 6/8 (12) | 0/4 (34) | 3/3 (6) | 87% |
| `qwen3:8b` think off | 10/12 (72) | 10/10 (76) | 5/5 (30) | 6/8 (21) | 0/4 (44) | 2/3 (14) | 79% |
| `qwen3:8b` think on | 12/12 (196) | 9/10 (190) | 3/5 (84) | 6/8 (208) | 1/4 (166) | 1/3 (94) | 79% |
| `llama3.1:8b` | 10/12 (43) | 7/10 (42) | 3/5 (18) | 8/8 (18) | 1/4 (32) | 1/3 (13) | 83% |
| `granite4.2:8b` think off | 7/12 (94) | 4/10 (96) | 5/5 (42) | 7/8 (30) | 0/4 (73) | 0/3 (23) | 75% |
| `granite4.2:8b` think on | 0/12, all timeouts | 0/10, all timeouts | 0/5 | 4/8 (645) | 0/4, all timeouts | 3/3 (142) | 75% |
| `ministral-3:8b` | 9/12 (109) | 9/10 (102) | 5/5 (37) | 6/8 (32) | 0/4 (81) | 0/3 (18) | 79% |
| `aya-expanse:8b` | 7/12 (75) | 7/10 (78) | 4/5 (31) | 6/8 (23) | 0/4 (45) | 0/3 (19) | 71% |
| `qwen3.5:9b` think off | 8/12 (76) | 8/10 (107) | 5/5 (32) | 7/8 (29) | 0/4 (62) | 3/3 (18) | 80% |
| `qwen3.5:9b` think on | 2/12, 10 timeouts | 0/10, all timeouts | 3/5 (91) | 4/8 (433) | 0/4, all timeouts | 3/3 (597) | 80% |

Shopping is almost never clean for any model: most flags are repeats, which the dedupe drops in the app.

### Chosen models

The app can run a model per task and reply language, so each test has its chosen model (`SELECTED` in `tools/compare_runs.py`), and a page without `--baseline` pairs a candidate with the model chosen for each sample's test and language:

| Test or language | Model | Why |
|---|---|---|
| Every test | `gemma4:e4b-it-qat` think off | Beat qwen2.5 17–3 |
| Shopping | `gemma4:e2b-it-q4_K_M` think on | Beat qwen2.5 2–0 in shopping; your pick |
| Turkish replies | `gemma4:e2b-it-q4_K_M` think on | Beat qwen2.5 5–0 on Turkish samples; your pick |

e4b think off also beat qwen2.5 on every Turkish sample, so `compare_selected__vs__gemma4_e4b-it-qat-think-off.html` puts the two gemmas head to head on shopping and Turkish.

### To fix in the chosen models

Found in the votes. When the models are chosen, add each one's code flags and the pairs it lost, then rework its prompts for them. The replies are in `tools/runs/models/<model>/<test>.json` and the run logs in `tools/runs/`.

- **Plan, fried** (`qwen2.5:7b`, run `2026-11-09_035602`): the cucumber, served as it is, gets a "Chop cucumber" step, and so does Eggs on toast, whose recipe doesn't use it. The `unlisted` check passes it, since cucumber is on the menu.
- **Plan, boiled** (`gemma4:e2b` think on, run `2026-11-09_205202`): butters the bread, then slices it, though it comes as slices (2 slice).
- **Suggest, sparse** (`gemma3:4b`, run `2026-11-09_065448`): bread twice, a slice in the omelette and 50 g served on its own.
- **Review, pancakes** (`qwen2.5:7b` and `gemma4:e4b` think off): swaps the blueberries for strawberries and keeps the name "Blueberry pancakes". A dish's name should follow its food.
- **Review, frittata** (`qwen2.5:7b` and `gemma4:e4b` think off): drops the smoked salmon, which nothing replaces, and keeps the name "Salmon frittata". The salmon should stay as written, marked missing, or the name should change. With the fuller samples (#188), e4b still drops it, adds spinach and renames the dish "Feta & Spinach Frittata", before and after #193 (runs `2026-11-10_050715`, `2026-11-10_051033`).
- **Review, omurice** (`gemma4:e4b` think off, both runs above): swaps the rice for pita bread and keeps the name "Omurice", a rice dish. The `named` label can't see it, since "rice" sits inside the word.
- **Prep words** (`gemma4:e4b` think off, the runs above and `2026-11-10_050918`, `2026-11-10_051219`): the reviser fills obvious forms with "N/A", "as is", "No prep needed" or "Cold". Prep words are for a form the dish needs.
- **Shopping, copied examples** (`gemma4:e2b` think on, runs `2026-11-10_050336`, `2026-11-10_050555`): the naming rule's examples come back as items, "Dried apricots" in 5 of the 8 presses and "Smoked salmon" in 4, before and after #190.

## Models

Fit is estimated for an 8192-token context: download size plus KV cache. LLMFIT is the
tool's verdict, run with an 8192-token context cap.

### 1. Fit on the GPU

| Model | Tag | Download | Fit | LLMFIT | Notes | Result |
|---|---|---|---|---|---|---|
| Qwen3 4B Instruct 2507 | `qwen3:4b-instruct-2507-q8_0` | 4.3 GB | 100% GPU | Perfect, ~46 tok/s | No thinking. `-q4_K_M` is 2.5 GB | |
| Gemma 3 4B | `gemma3:4b` | 3.4 GB | 100% GPU | Perfect (base model) | Strong across many languages | |
| Qwen3.5 4B 🧠 | `qwen3.5:4b` | 3.3–4.0 GB | 100% GPU | Perfect, ~40 tok/s | 2026, top 6 GB pick in several guides | Think off: code scores as the baseline, a little faster; Claude's blind votes 27–14 for it (2026-11-09) |
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
