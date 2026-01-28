@echo off
REM Simple double-click launcher for Gifts Bot dev stack
REM 1) Starts all services in background via PowerShell script
REM 2) Opens GUI log viewer (dev_gui.py)

cd /d "%~dp0"

REM Start all backend processes (API, webapp, tunnel, bot) in background
powershell -ExecutionPolicy Bypass -File ".\run-dev.ps1"

REM Start GUI log viewer (blocks until you close the window)
python "dev_gui.py"

pause

