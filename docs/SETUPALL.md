# break FAST — Full Server Setup Guide (Third PC)

This guide walks you through setting up the break FAST server on a fresh Windows
machine from scratch. By the end, you'll have:

- Ollama running locally with Qwen 2.5 7B
- The FastAPI backend serving the API
- The React frontend built and served statically by FastAPI
- A test user you can log in with
- Everything verified working end-to-end

Estimated time: 30-45 minutes (most of it is the model download).

---

## Step 0 — Install Prerequisites

Make sure these are installed before starting. If any are missing, install them now.

| Tool | Download | Verify with |
|---|---|---|
| **Git** | https://git-scm.com/downloads/win | `git --version` |
| **Python 3.11+** | https://www.python.org/downloads/ | `python --version` → 3.11 or newer |
| **Node.js 18+** | https://nodejs.org/ (LTS is fine) | `node --version` |
| **VS Code** | https://code.visualstudio.com/ | (optional but recommended) |

> **Python installer tip:** Check **"Add Python to PATH"** during install. If you
> forget, you'll need to add it manually to your system PATH later.

> **Node.js installer tip:** The LTS version is fine. Make sure `npm` is also on PATH
> (`npm --version` should work after install).

---

## Step 1 — Install Ollama

1. Download the Windows installer from: https://ollama.com/download/windows

2. Run the installer. It installs to `%LOCALAPPDATA%\Programs\Ollama` and adds itself
   to PATH automatically.

3. After install, Ollama starts as a background service automatically. Verify it's
   running:

   ```
   ollama --version
   ```

   You should see something like `ollama version 0.x.x`.

4. **Pull the Qwen 2.5 7B model** — this is the brain of the app. It's ~4.7 GB:

   ```
   ollama pull qwen2.5:7b
   ```

   This will take a while depending on your internet speed. Let it finish completely.

5. **Verify the model works:**

   ```
   ollama run qwen2.5:7b "Say good morning"
   ```

   You should get a short greeting back — this confirms the model is
   loaded and Ollama is functional.

6. **Verify the API is reachable:**

   ```
   curl http://localhost:11434/api/tags
   ```

   (If you don't have curl, open `http://localhost:11434/api/tags` in your browser.)
   You should see JSON listing `qwen2.5:7b` in the models array.

> **GPU note:** Ollama automatically detects NVIDIA GPUs and uses them. If you have a
> laptop GPU, it will use it — no extra configuration needed. You can verify with
> `ollama ps` after running a query to see if it says "GPU" in the processor column.

---

## Step 2 — Clone the Repository

Open a terminal (PowerShell or CMD) and navigate to where you want the project:

```
cd C:\Users\YourName\Projects
git clone https://github.com/theyoyoyo/breakFast.git
cd breakFast
```

From now on, all commands assume you're in the `breakFast` root directory (the one
containing `backend/`, `frontend/`, `CLAUDE.md`, etc.).

---

## Step 3 — Configure Environment Variables

1. Copy the example env file:

   ```
   copy .env.example .env
   ```

2. Open `.env` in VS Code (or any editor) and verify these values:

   ```
   # Ollama — these should be correct out of the box
   OLLAMA_BASE_URL=http://localhost:11434
   OLLAMA_MODEL=qwen2.5:7b

   # Database — stored in the backend folder
   DATABASE_PATH=./breakFAST.db

   # CORS — add your local IP here (find it in Step 8)
   # For now, localhost is enough for testing on this PC
   CORS_ORIGINS=http://localhost:5173,http://localhost:3000,http://localhost:8000

   # Serve built frontend from FastAPI (single-server production mode)
   SERVE_FRONTEND=true
   ```

   **The key difference from dev:** Set `SERVE_FRONTEND=true`. This tells the backend
   to serve the built React app as static files — one server, one port, no need for
   a separate frontend dev server.

   You don't need to change anything else for local testing. We'll add your LAN IP
   and Tailscale IP later.

---

## Step 4 — Install Backend Dependencies

```
cd backend
pip install -r requirements.txt
```

This installs FastAPI, uvicorn, aiosqlite, httpx, etc.

**Verify the install:**

```
python -c "import fastapi; print(fastapi.__version__)"
```

Should print `0.135.1` (or similar).

---

## Step 5 — Initialize the Database and Create a User

The database is created automatically when the backend starts, but you need at least
one user to log in. The admin CLI handles this:

```
cd backend
python manage.py add-user "Alice" --pin 1234 --admin
```

Replace `"Alice"` and `1234` with your name and desired PIN. The `--admin` flag gives
you admin privileges (needed for user management).

**Verify:**

```
python manage.py list-users
```

You should see your user listed.

> **Adding more users later:** Run `add-user` again with a different name/pin.
> Each user gets fully isolated data (ingredients, meals, preferences, etc.).

---

## Step 6 — Start the Backend and Test

Start the FastAPI server:

```
cd backend
python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

You should see output like:

```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

**Test the health endpoint:**

Open a new terminal and run:

```
curl http://localhost:8000/health
```

Should return: `{"status":"ok"}`

**Test authentication:**

```
curl -X POST http://localhost:8000/auth/login -H "Content-Type: application/json" -d "{\"name\": \"Alice\", \"pin\": \"1234\"}"
```

Should return JSON with a `token` field. Copy this token — you'll need it for the
next test.

**Test the Ollama connection through the backend:**

We'll test via the chat WebSocket, but first let's verify the backend can reach Ollama
by checking the health endpoint and then sending a test message through the API.

The chat uses WebSocket, which is harder to test from curl. We'll test it properly
from the browser in Step 8.

> **Keep this terminal running** — the backend needs to stay up. Open new terminals
> for the remaining steps.

---

## Step 7 — Build the Frontend for Production

Instead of running a dev server, we'll build the frontend as static files and serve
them from the FastAPI backend. This is the production setup — one server, one port.
All necessary config files are already in the repo.

1. **Install frontend dependencies:**

   ```
   cd frontend
   npm install
   ```

2. **Build the frontend:**

   ```
   npm run build
   ```

   This creates a `frontend/dist/` folder with the optimized static files.

   > **How it works:** The repo includes `frontend/.env.production` which sets
   > `VITE_BACKEND_URL=` (empty). This means the frontend calls the backend on
   > port 8000 of whatever host served it. Works for localhost, LAN IP, Tailscale IP,
   > all without rebuilding. And `SERVE_FRONTEND=true` in your `.env` tells the
   > backend to serve these files via a catch-all route.

3. **Restart the backend** (Ctrl+C the old one, then start again):

   ```
   cd backend
   python -m uvicorn main:app --host 0.0.0.0 --port 8000
   ```

4. **Test:** Open `http://localhost:8000` in your browser. You should see the
   break FAST login screen. Log in with your name and PIN.

---

## Step 8 — Full End-to-End Test

Now let's verify everything works together:

### 8.1 — Log in

Open `http://localhost:8000` in your browser. Enter your name and PIN. You should
land on the Chat tab.

### 8.2 — Test chat (Ollama integration)

Type a message like "Good morning!" and send it. If Ollama is running, you should get a
response streamed word-by-word (English by default; switch to Turkish in Settings). This confirms:

- Backend is running
- WebSocket connection works
- Ollama is reachable and responding
- The chat persona prompt is working

If you see a song lyric instead of a real response, it means Ollama is not reachable.
Go back to Step 1 and verify `ollama run qwen2.5:7b` works.

### 8.3 — Test the Fridge tab

Switch to the Fridge tab. Add some ingredients (e.g., "eggs", "white cheese",
"tomatoes"). They should appear grouped under "🍽️ Other" by default.

### 8.4 — Test meal suggestion

Go back to Chat and press the Suggest breakfast button (bottom of the chat). This
triggers the 3-step suggestion pipeline:

1. You should see progress indicators (drafting → analyzing → finalizing)
2. A menu suggestion should appear with its ingredients
3. A meal block should render inline in the chat

This is the most demanding test — it makes 3 sequential Ollama calls. If it works,
everything is functioning correctly.

### 8.5 — Test the Settings page

Go to Settings. Verify:

- Profile section shows empty fields (fill them in if you want)
- Kitchen sub-page shows 9 appliances with only Stove enabled
- Toggle some appliances on/off — they should persist after refresh

### 8.6 — Test from another device on the same network (optional)

1. Find this PC's local IP:

   ```
   ipconfig
   ```

   Look for `IPv4 Address` under your active network adapter (e.g., `192.168.1.x`).

2. Update CORS in `.env` to include the LAN IP:

   ```
   CORS_ORIGINS=http://localhost:5173,http://localhost:3000,http://localhost:8000,http://192.168.1.x:8000
   ```

   Restart the backend.

   > **No frontend rebuild needed** — the production build targets whichever host served it, so it
   > automatically talks to whatever host served it.

3. On your phone or another PC, open `http://192.168.1.x:8000` in the browser.

---

## Step 9 — Configure Kitchen Appliances

After logging in, go to **Settings → Kitchen**. You'll see 9 appliances:

| Appliance | Default |
|---|---|
| Stove | Enabled |
| Oven | Disabled |
| Air Fryer | Disabled |
| Toaster | Disabled |
| Microwave | Disabled |
| Blender | Disabled |
| Sandwich Press | Disabled |
| Kettle | Disabled |
| French Press | Disabled |

Enable the ones you actually own. This affects what the AI suggests — it will only
recommend meals you can prepare with your available appliances.

---

## Step 10 — Windows Firewall (if other devices can't connect)

If you can access the app on this PC but not from your phone/other devices, Windows
Firewall is likely blocking port 8000.

1. Open **Windows Defender Firewall** (search in Start menu)
2. Click **"Advanced settings"** on the left
3. Click **"Inbound Rules"** → **"New Rule..."** on the right
4. Choose **"Port"** → Next
5. Choose **"TCP"**, enter **8000** → Next
6. Choose **"Allow the connection"** → Next
7. Check all profiles (Domain, Private, Public) → Next
8. Name it **"breakFAST Backend"** → Finish

Now try accessing from your phone again.

---

## Troubleshooting

### "Cannot reach server" in the browser

- Is the backend running? Check the terminal where you started uvicorn.
- Are you using the right IP/port? Try `http://localhost:8000/health` first.
- If accessing from another device, did you open port 8000 in Windows Firewall?

### Chat returns song lyrics instead of real responses

This means Ollama is unreachable. Check:

1. Is Ollama running? `ollama --version` should work. If not, start it from the
   Start menu or run `ollama serve` in a terminal.
2. Can the backend reach it? `curl http://localhost:11434/api/tags` should return
   JSON with the model list.
3. Is the model pulled? `ollama list` should show `qwen2.5:7b`.

### Suggest button shows progress but then gives a weird/short response

The 3-step pipeline makes 3 sequential LLM calls. If the model is slow (no GPU or
limited RAM), it might time out. Check:

- `ollama ps` — shows if the model is loaded and which processor it's using.
  If it says "CPU", responses will be much slower (~30-60 seconds per step).
- If you have an NVIDIA GPU, make sure NVIDIA drivers are up to date. Ollama
  detects CUDA automatically.

### Frontend shows blank page at localhost:8000

- Did you build the frontend? (`cd frontend && npm run build`)
- Does `frontend/dist/` exist and contain files?
- Is `SERVE_FRONTEND=true` set in your `.env`? Restart the backend after changing it.

### "Module not found" errors when starting the backend

- Are you in the `backend/` directory when running uvicorn?
- Did you `pip install -r requirements.txt`?
- Are you using the right Python? `python --version` should be 3.11 or newer.

---

## BONUS A — Auto-Start on Boot

You don't need this for testing, but it's useful for daily use so the server is
always ready when you turn on the PC.

### Option 1: Task Scheduler (recommended)

1. Open **Task Scheduler** (search in Start menu)

2. Click **"Create Task..."** (not "Create Basic Task")

3. **General tab:**
   - Name: `breakFAST Server`
   - Check **"Run whether user is logged on or not"**
   - Check **"Run with highest privileges"**

4. **Triggers tab:**
   - New → Begin the task: **"At startup"**
   - Delay task for: **30 seconds** (gives Ollama time to start first)

5. **Actions tab:**
   - New → Action: **"Start a program"**
   - Program: `python`
   - Arguments: `-m uvicorn main:app --host 0.0.0.0 --port 8000`
   - Start in: `C:\Users\YourName\Projects\breakFast\backend`

6. **Conditions tab:**
   - Uncheck **"Start the task only if the computer is on AC power"**

7. Click OK. Enter your Windows password when prompted.

> **Ollama auto-starts by default** — it installs as a Windows service. You don't
> need to configure anything for it. Verify with `Get-Service OllamaService` in
> PowerShell after a reboot.

### Option 2: Startup Batch File (simpler)

The repo includes `start-server.bat` in the project root — it waits for Ollama,
checks connectivity, then starts the backend.

1. Press `Win + R`, type `shell:startup`, press Enter.

2. Right-click in the Startup folder → New → Shortcut.

3. Browse to `C:\Users\YourName\Projects\breakFast\start-server.bat`.

4. The batch file will run every time you log in.

> **Note:** This option requires you to be logged in. The Task Scheduler option
> works even without logging in.

---

## BONUS B — Tailscale (Remote Access)

Tailscale lets you access break FAST from anywhere — your phone on mobile data,
a laptop at a cafe, etc. It creates an encrypted tunnel directly between your
devices. No port forwarding, no dynamic DNS.

### B.1 — Install Tailscale on the third PC

1. Download from: https://tailscale.com/download/windows
2. Install and sign in with your Google/Microsoft/GitHub account.
3. After connecting, note your Tailscale IP:

   ```
   tailscale ip
   ```

   It'll be something like `100.x.x.x`.

### B.2 — Install Tailscale on your phone/other devices

1. Install the Tailscale app from Play Store (Android) or App Store (iOS).
2. Sign in with the **same account** as the third PC.
3. Both devices should appear in your Tailscale admin console:
   https://login.tailscale.com/admin/machines

### B.3 — Update break FAST config for Tailscale

1. **Update CORS** — add the Tailscale IP to your `.env`:

   ```
   CORS_ORIGINS=http://localhost:5173,http://localhost:3000,http://localhost:8000,http://192.168.1.x:8000,http://100.x.x.x:8000
   ```

   Replace `100.x.x.x` with your actual Tailscale IP.

2. **Restart the backend.** That's it — no frontend rebuild needed. The production
   build targets whichever host served it, so it works from any IP automatically.

### B.4 — Test from your phone

1. Make sure Tailscale is connected on your phone (green key icon in notification bar).
2. Open `http://100.x.x.x:8000` in your phone browser.
3. Log in and test — chat, suggestions, everything should work.

### B.5 — Configure Ollama for Tailscale (important!)

By default, Ollama only listens on `localhost`. If the backend and Ollama are on the
same machine (which they are), this is fine — the backend connects to
`localhost:11434` regardless of how *the user* reaches the backend.

**No Ollama configuration change is needed.** The backend always talks to Ollama
locally, even when a user connects via Tailscale.

---

## BONUS C — Test Prompts from Another PC (optional, for development)

`backend/tools/prompt_check.py` runs the real suggestion prompts from a development PC
against the server's Ollama and scores every reply in code. For that, Ollama on the
server has to accept connections from your Tailscale devices.

> **Ollama has no login.** Anyone who can reach port 11434 can use the model, and also
> pull or delete models. Open it to your Tailscale network only. Never forward the
> port on your router.

### C.1 — Let Ollama listen beyond localhost (server)

1. Set the environment variable `OLLAMA_HOST` to `0.0.0.0:11434`, in a terminal:

   ```
   setx OLLAMA_HOST 0.0.0.0:11434
   ```

2. Quit Ollama from the tray icon and start it again (or restart the PC).

The backend on the server keeps using `localhost:11434`; nothing else changes.

### C.2 — Allow the port from Tailscale only (server)

In an **administrator** PowerShell:

```powershell
New-NetFirewallRule -DisplayName "Ollama (Tailscale only)" -Direction Inbound -Protocol TCP -LocalPort 11434 -RemoteAddress 100.64.0.0/10 -InterfaceAlias "Tailscale" -Action Allow
```

The rule only lets in traffic that arrives through the Tailscale adapter from a Tailscale
address (`100.64.0.0/10`), so other devices on your home network can't reach Ollama, not
even by giving themselves a 100.x address. `Get-NetAdapter` shows the adapter's name if
yours isn't `Tailscale`. If Windows asks whether to allow Ollama on networks, choose
**Cancel**: the rule above is all it needs. Keep Ollama updated, since it is now
reachable from your other devices.

### C.3 — Run the prompt test (development PC)

1. Check the connection; it should list `qwen2.5:7b`:

   ```
   curl http://100.x.x.x:11434/api/tags
   ```

2. From `backend/`:

   ```
   python -m tools.prompt_check --url http://100.x.x.x:11434
   ```

   Options: `--runs 5`, `--samples tr`, `--mode explore`, `--draft` (stop after the
   draft). Setting `OLLAMA_BASE_URL` in the development PC's `backend/.env` saves the `--url`.

3. Each run is one Suggest press for a sample user (`tools/prompt_samples.py`). The
   table counts, for the draft and the final reply, how many replies were clean (meal
   JSON parses, nothing missing from the fridge, no prepared item served as one fridge
   item, only listed units), then lists the most frequent problems. The replies are saved
   to `backend/tools/runs/` with the commit they ran on, so run it before and after a
   prompt change.

Runs share the server's GPU, so the app is slower meanwhile; 10 runs per sample take
several minutes.

---

## Quick Reference

| What | Command / URL |
|---|---|
| Start backend | `cd backend && python -m uvicorn main:app --host 0.0.0.0 --port 8000` |
| Build frontend | `cd frontend && npm run build` |
| Add user | `cd backend && python manage.py add-user "Name" --pin 1234 --admin` |
| List users | `cd backend && python manage.py list-users` |
| Backup DB | `cd backend && python manage.py backup-db` |
| Check Ollama | `ollama list` |
| Test Ollama | `ollama run qwen2.5:7b "Good morning"` |
| Prompt test (dev PC) | `cd backend && python -m tools.prompt_check --url http://100.x.x.x:11434` |
| Health check | `curl http://localhost:8000/health` |
| Logs | Check the terminal where uvicorn is running |
| DB location | `backend/breakFAST.db` (or wherever DATABASE_PATH points) |
