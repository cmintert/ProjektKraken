@echo off
rem Switch to the script's directory
cd /d "%~dp0"

echo Starting Projekt Kraken...

if exist ".venv\Scripts\python.exe" (
    rem Run the application using the virtual environment's Python
    ".venv\Scripts\python.exe" -m src.app.main
) else (
    echo Virtual environment not found at .venv
    echo Please ensure you have set up the environment:
    echo 1. python -m venv .venv
    echo 2. .venv\Scripts\activate
    echo 3. pip install -r requirements.txt
    pause
    exit /b 1
)

if %ERRORLEVEL% NEQ 0 (
    echo Application exited with error code %ERRORLEVEL%
    pause
)
