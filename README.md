# break FAST

A personal AI-powered breakfast planner. Knows your ingredients, your kitchen, and your health context. Suggests the richest, healthiest, most efficiently prepared breakfast each morning with minimal friction.

---

## Setup (Third PC — Backend)

### Prerequisites

- Python 3.11+ (tested with 3.14)
- Node.js 18+ (for frontend)
- [Ollama](https://ollama.ai) — optional, only needed for local LLM

### Quick Start (without LLM)

You can run the app without Ollama or an API key. The UI and all CRUD features (ingredients, meals, preferences) will work — only the chat/suggestion engine requires an LLM connection.

```bash
# 1. Setup
cp .env.example .env
cd backend && pip install -r requirements.txt
cd ../frontend && npm install

# 2. Run (two terminals)
cd backend && python -m uvicorn main:app --host 0.0.0.0 --port 8000
cd frontend && npm run dev
```

Open http://localhost:5173 in your browser.

### Full Setup (with LLM)

### 1. Pull the Ollama model

```bash
ollama pull llama3.1:8b
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env — set ANTHROPIC_API_KEY if you want the Claude fallback
```

### 3. Install backend dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 4. Start the backend

```bash
cd backend
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

The backend is now reachable at `http://<third-pc-ip>:8000`.

---

## Setup (Frontend — any machine)

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173` in your browser.

For phone access on home WiFi, open `http://<third-pc-ip>:5173` (Vite will need `--host` flag or set `server.host = true` in `vite.config.js`).

---

## Remote Access via Tailscale

Install Tailscale on the third PC and on your phone/laptop. Once connected, the backend is accessible at the Tailscale IP (`100.x.x.x:8000`) from anywhere, encrypted end-to-end. No port forwarding needed.

---

## Architecture

```
[Phone / Desktop — browser]
         |
         | HTTP / WebSocket
         v
 [FastAPI Backend — third PC]
   |               |
   v               v
[Ollama]    [Claude API fallback]
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
| LLM Fallback | Anthropic Claude API |
| Database | SQLite |
| Voice | Web Speech API |
| Nutrition | Open Food Facts API |
| Remote Access | Tailscale |
