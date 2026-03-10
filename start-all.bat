@echo off
title Content Engine AI - Launcher
cd /d %~dp0

echo Starting API Server...
start "API Server" cmd /k "cd /d %~dp0 && call .venv\Scripts\activate && python run.py"

echo Starting Temporal Worker...
start "Temporal Worker" cmd /k "cd /d %~dp0 && call .venv\Scripts\activate && python -m app.temporal.worker"

echo.
echo Both services started in separate windows.
echo   API Server:      http://localhost:8000
echo   Swagger Docs:    http://localhost:8000/docs
echo   Temporal Worker:  connected to Temporal Cloud
echo.
pause
