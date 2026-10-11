@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (echo Run install_voltmind.bat once first.& exit /b 1)
".venv\Scripts\python.exe" scripts\launcher.py start %*
exit /b %errorlevel%
