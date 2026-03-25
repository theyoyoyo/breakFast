# break FAST — Full Server Setup Guide (Third PC)

This guide walks you through setting up the break FAST server on a fresh Windows
machine from scratch. By the end, you'll have:

- Ollama running locally with Llama 3.1 8B
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
| **Python 3.14** | https://www.python.org/downloads/ | `python --version` → 3.14.x |
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

4. **Pull the Llama 3.1 8B model** — this is the brain of the app. It's ~4.7 GB:

   ```
   ollama pull llama3.1:8b
   ```

   This will take a while depending on your internet speed. Let it finish completely.

5. **Verify the model works:**

   ```
   ollama run llama3.1:8b "Say hello in Turkish"
   ```

   You should get a Turkish response like "Merhaba!" — this confirms the model is
   loaded and Ollama is functional.

6. **Verify the API is reachable:**

   ```
   curl http://localhost:11434/api/tags
   ```

   (If you don't have curl, open `http://localhost:11434/api/tags` in your browser.)
   You should see JSON listing `llama3.1:8b` in the models array.

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
   OLLAMA_MODEL=llama3.1:8b

   # Database — stored in the backend folder
   DATABASE_PATH=./breakFAST.db

   # Backend — listen on all interfaces so other devices can connect
   BACKEND_HOST=0.0.0.0
   BACKEND_PORT=8000

   # CORS — add your local IP here (find it in Step 8)
   # For now, localhost is enough for testing on this PC
   CORS_ORIGINS=http://localhost:5173,http://localhost:3000,http://localhost:8000
   ```

   You don't need to change anything for local testing. We'll add your LAN IP and
   Tailscale IP later.

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
python manage.py add-user "Onur" --pin 1234 --admin
```

Replace `"Onur"` and `1234` with your name and desired PIN. The `--admin` flag gives
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
curl -X POST http://localhost:8000/auth/login -H "Content-Type: application/json" -d "{\"name\": \"Onur\", \"pin\": \"1234\"}"
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

1. **Install frontend dependencies:**

   ```
   cd frontend
   npm install
   ```

2. **Set the backend URL for the build:**

   The frontend needs to know where the backend lives. For production, it's the same
   origin (served by FastAPI), so we set it to empty string or the actual URL.

   Create a `.env.production` file in the `frontend/` folder:

   ```
   echo VITE_BACKEND_URL=http://localhost:8000 > .env.production
   ```

   > **Important:** When you later access from your phone or via Tailscale, you'll
   > need to rebuild with the correct URL (your PC's LAN IP or Tailscale IP). See
   > Step 8 for details.

3. **Build the frontend:**

   ```
   npm run build
   ```

   This creates a `frontend/dist/` folder with the optimized static files.

4. **Serve the frontend from FastAPI:**

   We need to tell FastAPI to serve these static files. Add a static file mount to
   the backend. Open `backend/main.py` and add these lines:

   **At the top, add the import:**

   ```python
   from fastapi.staticfiles import StaticFiles
   from fastapi.responses import FileResponse
   from pathlib import Path
   ```

   **At the bottom of the file (after all router includes), add:**

   ```python
   # Serve frontend static files in production
   _frontend_dist = Path(__file__).parent.parent / "frontend" / "dist"
   if _frontend_dist.exists():
       app.mount("/assets", StaticFiles(directory=str(_frontend_dist / "assets")), name="static")

       @app.get("/{full_path:path}")
       async def serve_frontend(full_path: str):
           """Serve the React SPA for any non-API route."""
           file_path = _frontend_dist / full_path
           if file_path.exists() and file_path.is_file():
               return FileResponse(str(file_path))
           return FileResponse(str(_frontend_dist / "index.html"))
   ```

   > **Why this works:** API routes (`/health`, `/auth/*`, `/chat`, etc.) are
   > registered before the catch-all `/{full_path}`, so they take priority. Any
   > non-API URL serves the React SPA, which handles its own routing.

5. **Restart the backend** (Ctrl+C the old one, then start again):

   ```
   cd backend
   python -m uvicorn main:app --host 0.0.0.0 --port 8000
   ```

6. **Test:** Open `http://localhost:8000` in your browser. You should see the
   break FAST login screen. Log in with your name and PIN.

---

## Step 8 — Full End-to-End Test

Now let's verify everything works together:

### 8.1 — Log in

Open `http://localhost:8000` in your browser. Enter your name and PIN. You should
land on the Chat tab.

### 8.2 — Test chat (Ollama integration)

Type a message like "Merhaba!" and send it. If Ollama is running, you should get a
Turkish response streamed word-by-word. This confirms:

- Backend is running
- WebSocket connection works
- Ollama is reachable and responding
- The chat persona prompt is working

If you see a song lyric instead of a real response, it means Ollama is not reachable.
Go back to Step 1 and verify `ollama run llama3.1:8b` works.

### 8.3 — Test the Fridge tab

Switch to the Fridge tab. Add some ingredients (e.g., "yumurta", "beyaz peynir",
"domates"). They should appear grouped under "Diger" by default.

### 8.4 — Test meal suggestion

Go back to Chat and press the "Kahvalti Oner" button (bottom of the chat). This
triggers the 3-step suggestion pipeline:

1. You should see progress indicators (drafting → analyzing → finalizing)
2. A full Turkish meal suggestion should appear with ingredients and steps
3. A meal block should render inline in the chat

This is the most demanding test — it makes 3 sequential Ollama calls. If it works,
everything is functioning correctly.

### 8.5 — Test the Settings page

Go to Settings. Verify:

- Profile section shows empty fields (fill them in if you want)
- Kitchen sub-page shows 9 appliances with only Ocak enabled
- Toggle some appliances on/off — they should persist after refresh

### 8.6 — Test from another device on the same network (optional)

1. Find this PC's local IP:

   ```
   ipconfig
   ```

   Look for `IPv4 Address` under your active network adapter (e.g., `192.168.1.x`).

2. Update the frontend build with the correct URL:

   Edit `frontend/.env.production`:

   ```
   VITE_BACKEND_URL=http://192.168.1.x:8000
   ```

   Rebuild:

   ```
   cd frontend
   npm run build
   ```

   Restart the backend.

3. Update CORS in `.env`:

   ```
   CORS_ORIGINS=http://localhost:5173,http://localhost:3000,http://localhost:8000,http://192.168.1.x:8000
   ```

   Restart the backend again.

4. On your phone or another PC, open `http://192.168.1.x:8000` in the browser.

---

## Step 9 — Configure Kitchen Appliances

After logging in, go to **Settings → Kitchen**. You'll see 9 appliances:

| Appliance | Turkish Name | Default |
|---|---|---|
| Stove | Ocak | Enabled |
| Oven | Firin | Disabled |
| Air Fryer | Airfryer | Disabled |
| Toaster | Ekmek Kizartma Makinesi | Disabled |
| Microwave | Mikrodalga | Disabled |
| Blender | Blender | Disabled |
| Sandwich Press | Tost Makinesi | Disabled |
| Kettle | Su Isitici | Disabled |
| French Press | French Press | Disabled |

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
3. Is the model pulled? `ollama list` should show `llama3.1:8b`.

### "Kahvalti Oner" button shows progress but then gives a weird/short response

The 3-step pipeline makes 3 sequential LLM calls. If the model is slow (no GPU or
limited RAM), it might time out. Check:

- `ollama ps` — shows if the model is loaded and which processor it's using.
  If it says "CPU", responses will be much slower (~30-60 seconds per step).
- If you have an NVIDIA GPU, make sure NVIDIA drivers are up to date. Ollama
  detects CUDA automatically.

### Frontend shows blank page at localhost:8000

- Did you build the frontend? (`cd frontend && npm run build`)
- Does `frontend/dist/` exist and contain files?
- Did you add the static file serving code to `backend/main.py`? (Step 7.4)

### "Module not found" errors when starting the backend

- Are you in the `backend/` directory when running uvicorn?
- Did you `pip install -r requirements.txt`?
- Are you using the right Python? `python --version` should be 3.14.x.

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

1. Create a file called `start-server.bat` in the project root:

   ```bat
   @echo off
   echo Waiting for Ollama to start...
   timeout /t 15 /nobreak >nul

   echo Starting break FAST backend...
   cd /d C:\Users\YourName\Projects\breakFast\backend
   python -m uvicorn main:app --host 0.0.0.0 --port 8000
   ```

2. Press `Win + R`, type `shell:startup`, press Enter.

3. Create a shortcut to `start-server.bat` in the Startup folder.

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

2. **Rebuild the frontend** with the Tailscale URL:

   Edit `frontend/.env.production`:

   ```
   VITE_BACKEND_URL=http://100.x.x.x:8000
   ```

   Then rebuild:

   ```
   cd frontend
   npm run build
   ```

   > **Caveat:** The frontend URL is baked into the build. If you want it to work
   > from both LAN (`192.168.1.x`) and Tailscale (`100.x.x.x`), you have two
   > options:
   >
   > 1. Always use the Tailscale IP (works on LAN too since Tailscale routes locally)
   > 2. Set `VITE_BACKEND_URL=` (empty) and access via the backend URL directly —
   >    since we serve the frontend from FastAPI, relative URLs will work.
   >
   > **Option 2 is recommended** — set `VITE_BACKEND_URL=` to empty string in
   > `.env.production` and rebuild. This way the frontend always talks to whatever
   > host served it.

3. **Restart the backend.**

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

## Quick Reference

| What | Command / URL |
|---|---|
| Start backend | `cd backend && python -m uvicorn main:app --host 0.0.0.0 --port 8000` |
| Build frontend | `cd frontend && npm run build` |
| Add user | `cd backend && python manage.py add-user "Name" --pin 1234 --admin` |
| List users | `cd backend && python manage.py list-users` |
| Backup DB | `cd backend && python manage.py backup-db` |
| Check Ollama | `ollama list` |
| Test Ollama | `ollama run llama3.1:8b "Merhaba"` |
| Health check | `curl http://localhost:8000/health` |
| Logs | Check the terminal where uvicorn is running |
| DB location | `backend/breakFAST.db` (or wherever DATABASE_PATH points) |
