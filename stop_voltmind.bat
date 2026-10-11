@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (echo No local environment exists.& exit /b 0)
".venv\Scripts\python.exe" scripts\launcher.py stop
exit /b %errorlevel%
