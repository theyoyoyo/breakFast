@echo off
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

echo === Setup complete! Run start.bat to launch the app. ===
pause
