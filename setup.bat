@echo off
cd /d "%~dp0"
echo === break FAST — First-time Setup ===
echo.

REM Copy .env if missing
if not exist ".env" (
    echo Copying .env.example to .env...
    copy .env.example .env
    echo Done. Edit .env if needed.
    echo.
)

REM Backend dependencies
echo Installing backend dependencies...
cd backend
pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: pip install failed. Make sure Python 3.11+ is on PATH.
    pause
    exit /b 1
)
cd ..
echo Backend dependencies installed.
echo.

REM Frontend dependencies
echo Installing frontend dependencies...
cd frontend
npm install
if errorlevel 1 (
    echo ERROR: npm install failed. Make sure Node.js 18+ is on PATH.
    pause
    exit /b 1
)
cd ..
echo Frontend dependencies installed.
echo.

REM Pull the Ollama model
echo Pulling LLM model (qwen2.5:7b) — this may take a few minutes on first run...
ollama pull qwen2.5:7b
if errorlevel 1 (
    echo WARNING: Could not pull model. Make sure Ollama is installed and running.
    echo Download Ollama from https://ollama.com then re-run setup.bat.
)
echo.

echo === Setup complete! Run start.bat to launch the app. ===
pause
