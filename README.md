# break FAST

A personal AI-powered breakfast planner. Knows your ingredients, your kitchen, and your health context. Suggests the richest, healthiest, most efficiently prepared breakfast each morning with minimal friction. Multi-user, local-first, free forever.

---

## Setup

### Prerequisites

- Python 3.11+
- Node.js 18+
- [Ollama](https://ollama.ai) — optional, only needed for AI chat/suggestions

### Quick start (Windows)

Double-click `start.bat`. It opens the backend and frontend in separate terminal windows.

### Manual start

```bash
# Backend
cd backend && pip install -r requirements.txt
python -m uvicorn main:app --host 0.0.0.0 --port 8000

# Frontend (separate terminal)
cd frontend && npm install && npm run dev
```

Open `http://localhost:5173` in your browser.

### With Ollama (local LLM)

```bash
ollama pull llama3.1:8b
cp .env.example .env   # adjust OLLAMA_BASE_URL if needed
```

The app works without Ollama — all CRUD features run fine. Only chat and meal suggestions require an LLM.

---

## User Management (admin CLI)

Users are managed from the command line on the server machine. Each user gets their own PIN.

```bash
cd backend
python manage.py add-user "Onur" --pin 1234
python manage.py list-users
python manage.py delete-user "Onur"
python manage.py backup-db
```

Users log in from the browser with their name and PIN. Sessions are device-independent (works from phone and desktop with the same account).

---

## Remote Access

Install [Tailscale](https://tailscale.com) on the server PC and your devices. The backend becomes accessible at the Tailscale IP (`100.x.x.x:8000`) from anywhere — encrypted, no port forwarding needed.

For phone access on home WiFi: `http://<server-ip>:5173` (Vite serves on `0.0.0.0` by default).

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

## Tech Stack

| Layer | Choice |
|---|---|
| Frontend | React PWA (Vite) |
| Backend | Python / FastAPI |
| Local LLM | Ollama + Llama 3.1 8B |
| LLM Fallback | Song lyric cycling (when Ollama is unreachable) |
| Database | SQLite |
| Voice | Web Speech API (browser-native) |
| Nutrition | Open Food Facts API |
| Remote Access | Tailscale |
