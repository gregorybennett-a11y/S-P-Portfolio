@echo off
cd /d "%~dp0sp500"

:: Check if launcher already running
curl -s --max-time 1 http://localhost:8766/ping >nul 2>&1
if %ERRORLEVEL%==0 (
    echo [OK] Launcher already running on http://localhost:8766
    timeout /t 2 >nul
    exit /b 0
)

:: Try pythonw first — no console window
where pythonw >nul 2>&1
if %ERRORLEVEL%==0 (
    start "" /B pythonw launcher.py
    echo [OK] Launcher started silently in background ^(port 8766^).
    timeout /t 2 >nul
    exit /b 0
)

:: Fallback — minimized window
start "Portfolio Launcher" /min python launcher.py
echo [OK] Launcher started ^(minimized window^).
timeout /t 2 >nul
