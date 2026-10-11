@echo off
setlocal
cd /d "%~dp0"
".venv\Scripts\python.exe" -m pytest tests -q --junitxml=reports\python_tests.xml || exit /b 1
".venv\Scripts\python.exe" scripts\validate_robustness.py || exit /b 1
pushd frontend
node --test tests\history.test.mjs tests\reports.test.mjs tests\waveforms.test.mjs tests\monitoringInsights.test.mjs
if errorlevel 1 (popd & exit /b 1)
call npm.cmd run build
if errorlevel 1 (popd & exit /b 1)
popd
pushd backend
call mvnw.cmd -B test
if errorlevel 1 (popd & exit /b 1)
popd
echo Source/runtime/build checks passed. Use tests\final_http_workflow.py against an isolated test instance for real HTTP acceptance checks.
