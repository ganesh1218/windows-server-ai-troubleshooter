@echo off
setlocal
cd /d "%~dp0"
title ServerScope - Real Server Health Check
if not exist "dashboard.zip" (
  echo Bundled dashboard missing. Ask your administrator to restore dashboard.zip in this project folder.
  pause
  exit /b 1
)
echo Starting the REAL local Server Health Check.
echo Keep this window open. The browser establishes its local session automatically.
echo Enter your actual server name or IP and Windows credentials in the local browser.
echo Press Ctrl+C here to stop the application.
powershell.exe -NoProfile -File "%~dp0scripts\Start-HealthCheck.ps1"
pause
