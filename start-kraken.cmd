@echo off
setlocal
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" launcher.py %*
    goto :finished
)

py -3.13 -c "import sys" >nul 2>&1
if not errorlevel 1 (
    py -3.13 launcher.py %*
    goto :finished
)

python -c "import sys" >nul 2>&1
if not errorlevel 1 (
    python launcher.py %*
    goto :finished
)

echo.
echo ProjektKraken could not find Python 3.13.
echo Install Python 3.13 or create .venv in this project folder.
set "KRAKEN_EXIT_CODE=1"
goto :failed

:finished
set "KRAKEN_EXIT_CODE=%ERRORLEVEL%"
if "%KRAKEN_EXIT_CODE%"=="0" goto :end

:failed
echo.
echo ProjektKraken exited with an error ^(code %KRAKEN_EXIT_CODE%^).
echo Check the newest logs\faults.*.log and logs\kraken.*.log for details.
echo For startup failures, also check logs\startup_error.log and its timestamp.
echo.
pause

:end
exit /b %KRAKEN_EXIT_CODE%
