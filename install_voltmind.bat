@echo off
setlocal
cd /d "%~dp0"
echo VoltMind installation
echo Folder: %CD%
echo.
call :install
set "install_result=%errorlevel%"
echo.
if "%install_result%"=="0" (
  echo Installation complete. Run start_voltmind.bat.
) else (
  echo Installation failed. Read the error above before closing this window.
)
if /i not "%~1"=="--no-pause" pause
exit /b %install_result%

:install
echo [1/5] Checking Python, Java and Node.js...
where python >nul 2>nul || (echo Python 3.12 or 3.13 is required on PATH. See START_HERE.md.& exit /b 1)
where java >nul 2>nul || (echo Java JDK 17 or newer is required on PATH. See START_HERE.md.& exit /b 1)
where node >nul 2>nul || (echo Node.js 22 or newer is required on PATH. See START_HERE.md.& exit /b 1)
python -c "import pathlib,sys; p=str(pathlib.Path.cwd()); print('Use a shorter extraction folder, such as Desktop\VoltMind, to avoid Windows package path limits.' if len(p)>90 else 'Extraction path checked.'); sys.exit(1 if len(p)>90 else 0)"
if errorlevel 1 exit /b 1
echo [2/5] Creating the Python environment. This step can take a few minutes...
python -m venv .venv || exit /b 1
echo [3/5] Installing Python packages. Internet access is needed on the first run...
".venv\Scripts\python.exe" -u -m pip install -r requirements-dev.txt || exit /b 1
echo [4/5] Installing and building the frontend...
pushd frontend
call npm.cmd ci
if errorlevel 1 (popd & exit /b 1)
call npm.cmd run build
if errorlevel 1 (popd & exit /b 1)
popd
echo [5/5] Testing and packaging the Spring Boot backend...
pushd backend
call mvnw.cmd -B test package
if errorlevel 1 (popd & exit /b 1)
popd
exit /b 0
