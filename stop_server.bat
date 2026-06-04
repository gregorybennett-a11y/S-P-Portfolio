@echo off
:: Kill any python process running sp500_server.py
for /f "tokens=2" %%a in ('tasklist /fi "imagename eq python.exe" /fo list ^| findstr PID') do (
    wmic process %%a get commandline 2>nul | findstr /i "sp500_server" >nul
    if %ERRORLEVEL%==0 (
        taskkill /PID %%a /F >nul 2>&1
        echo [OK] Server stopped.
        exit /b 0
    )
)
for /f "tokens=2" %%a in ('tasklist /fi "imagename eq pythonw.exe" /fo list ^| findstr PID') do (
    wmic process %%a get commandline 2>nul | findstr /i "sp500_server" >nul
    if %ERRORLEVEL%==0 (
        taskkill /PID %%a /F >nul 2>&1
        echo [OK] Server stopped.
        exit /b 0
    )
)
echo Server was not running.
timeout /t 2 >nul
