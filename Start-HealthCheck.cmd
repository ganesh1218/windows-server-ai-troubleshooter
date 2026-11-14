@echo off
setlocal
cd /d "%~dp0"
title ServerScope - Real Server Health Check
if not exist ".venv\Scripts\python.exe" (
  echo Python environment missing. Follow the installation steps in README.md first.
  pause
  exit /b 1
)
if not exist "dist\index.html" (
  echo Dashboard build missing. Run npm ci and npm run build first.
  pause
  exit /b 1
)
echo Starting the REAL local Server Health Check.
echo Keep this window open. The browser establishes its local session automatically.
echo Enter your actual server name or IP and Windows credentials in the local browser.
echo Press Ctrl+C here to stop the application.
".venv\Scripts\python.exe" -m backend.app --open-browser
pause
