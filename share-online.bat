@echo off
title SENTRY — share online (ngrok tunnel)
cd /d "%~dp0"

REM ===== first-time setup (skip if already done) =====
REM 1. Create a free account at https://dashboard.ngrok.com/signup
REM 2. Download ngrok.exe from https://ngrok.com/download and put it in this folder
REM 3. Run once:  ngrok config add-authtoken YOUR_TOKEN  (from the ngrok dashboard)
REM 4. Claim your free static domain in the ngrok dashboard (Universal Static Domain)
REM 5. Paste it below between the = signs, e.g. set "NGROK_DOMAIN=sparksabhi-sentry.ngrok-free.app"

set "NGROK_DOMAIN=YOUR-STATIC-DOMAIN.ngrok-free.app"

if not exist "ngrok.exe" (
  echo ngrok.exe not found in this folder.
  echo Download it from https://ngrok.com/download and place it here, then re-run.
  start "" https://ngrok.com/download
  pause
  exit /b 1
)

if "%NGROK_DOMAIN%"=="YOUR-STATIC-DOMAIN.ngrok-free.app" (
  echo First time: edit this file and set NGROK_DOMAIN to your free static domain
  echo from https://dashboard.ngrok.com/domains  ^(claim one, then paste it here^).
  start "" https://dashboard.ngrok.com/domains
  pause
  exit /b 1
)

REM start the SENTRY server if it is not already running
curl -s --max-time 2 http://127.0.0.1:8901/api/health > nul 2>&1
if errorlevel 1 (
  echo Starting SENTRY backend...
  start "SENTRY backend" cmd /c ""%~dp0.venv\Scripts\python.exe" -m uvicorn main:app --port 8901 --app-dir "%~dp0backend""
  timeout /t 10 /nobreak > nul
) else (
  echo SENTRY backend already running.
)

echo.
echo Sharing SENTRY on your permanent public link:
echo   https://%NGROK_DOMAIN%
echo (laptop must stay on + this window open; press Ctrl+C to stop sharing)
echo.
ngrok http --url=%NGROK_DOMAIN% 8901
