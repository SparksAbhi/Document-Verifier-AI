@echo off
title SENTRY backend
cd /d "%~dp0"
echo Starting SENTRY backend on http://127.0.0.1:8901 ...
echo (First request after start is slower while AI models load - that's normal.)
echo.
".venv\Scripts\python.exe" -m uvicorn main:app --port 8901 --app-dir "backend"
pause
