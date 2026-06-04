@echo off
:: Adds start_server.bat to Windows startup so the server auto-runs on login

set STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup
set BAT_PATH=%~dp0start_server.bat

:: Create a VBScript launcher (so no flash of a cmd window on startup)
set VBS_PATH=%STARTUP%\SP500_Server.vbs

echo Set WshShell = CreateObject("WScript.Shell") > "%VBS_PATH%"
echo WshShell.Run Chr(34) ^& "%BAT_PATH%" ^& Chr(34), 0, False >> "%VBS_PATH%"

echo [OK] Added to Windows startup.
echo      The server will now start automatically when you log in.
echo      File: %VBS_PATH%
echo.
echo      To remove from startup, delete:
echo      %VBS_PATH%
timeout /t 4 >nul
