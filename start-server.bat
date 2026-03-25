@echo off
echo ============================================
echo   break FAST — Production Server
echo ============================================
echo.

REM Wait for Ollama to be ready (it starts as a Windows service)
echo Waiting for Ollama...
timeout /t 10 /nobreak >nul

REM Verify Ollama is reachable
curl -s http://localhost:11434/api/tags >nul 2>&1
if %errorlevel% neq 0 (
    echo WARNING: Ollama is not reachable. Chat will use lyric fallback.
    echo Start Ollama manually if needed.
    echo.
)

echo Starting backend (serves API + frontend)...
echo Access at: http://localhost:8000
echo.

cd /d %~dp0backend
python -m uvicorn main:app --host 0.0.0.0 --port 8000
