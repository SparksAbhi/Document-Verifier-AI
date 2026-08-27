@echo off
title SENTRY setup
cd /d "%~dp0"
echo Creating virtual environment (this takes a minute)...
python -m venv .venv
if errorlevel 1 (
  echo Python not found. Install Python 3.11+ from python.org and re-run.
  pause
  exit /b 1
)
echo Installing dependencies (first run downloads ~4GB of AI libraries)...
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r backend\requirements.txt
if not exist "backend\dbconfig.py" (
  echo.
  echo ERROR: backend\dbconfig.py not found.
  echo Copy backend\dbconfig.example.py to backend\dbconfig.py and paste in
  echo the Neon connection string from the team lead.
  pause
  exit /b 1
)
echo Generating sample documents...
".venv\Scripts\python.exe" backend\samples\generate_samples.py
echo.
echo Setup complete! Run start-sentry.bat to launch.
pause
