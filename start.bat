@echo off
echo Starting break FAST...
echo.

start "breakFAST-backend" cmd /k "cd backend && python -m uvicorn main:app --host 0.0.0.0 --port 8000"
timeout /t 2 /nobreak >nul
start "breakFAST-frontend" cmd /k "cd frontend && npm run dev"

echo Both servers starting. Check the opened windows.
echo Backend: http://localhost:8000
echo Frontend: http://localhost:5173
