@echo off
cd /d "d:\RailGPT\railgpt-project"
echo ================================================================
echo   RailGPT - Railway Dispatch AI Assistant
echo ================================================================
echo.
echo Starting backend server...
start "RailGPT Backend" cmd /c "python backend.py"
echo Waiting for backend to initialize (5s)...
timeout /t 5 /nobreak >nul
echo Starting frontend...
start "RailGPT Frontend" cmd /c "python frontend.py"
echo.
echo Both services started. The app window will open shortly.
echo Keep the two console windows open while using the app.
echo.
