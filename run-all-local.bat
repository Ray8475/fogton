@echo off
setlocal

REM Определяем корень проекта (папка, где лежит этот .bat)
set "ROOT=%~dp0"
REM убираем завершающий обратный слеш
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"

echo Project root: %ROOT%

REM Проверяем, заняты ли порты
echo Checking if ports are available...
netstat -ano | findstr ":8000" >nul 2>&1
if %errorlevel% equ 0 (
    echo WARNING: Port 8000 is already in use!
    echo Killing processes on port 8000...
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000" ^| findstr "LISTENING"') do (
        taskkill /PID %%a /F >nul 2>&1
    )
    timeout /t 1 /nobreak >nul
)

netstat -ano | findstr ":8081" >nul 2>&1
if %errorlevel% equ 0 (
    echo WARNING: Port 8081 is already in use!
    echo Killing processes on port 8081...
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8081" ^| findstr "LISTENING"') do (
        taskkill /PID %%a /F >nul 2>&1
    )
    timeout /t 1 /nobreak >nul
)

echo Starting API (uvicorn) on http://0.0.0.0:8000 ...
REM /k чтобы окно не закрывалось сразу при ошибке
start "api" /D "%ROOT%\backend" cmd /k python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --timeout-keep-alive 75

echo Starting bot (run_bot.py) ...
REM /k чтобы видеть traceback, если бот упадёт
start "bot" /D "%ROOT%" cmd /k python run_bot.py

echo Starting Cloudflare Tunnel (cloudflared) ...
REM Читаем токен из .env файла через PowerShell (более надёжно)
set "TUNNEL_TOKEN="
for /f "delims=" %%i in ('powershell -Command "if (Test-Path '%ROOT%\.env') { Get-Content '%ROOT%\.env' | Where-Object { $_ -match '^CLOUDFLARED_TUNNEL_TOKEN=(.+)$' } | ForEach-Object { $matches[1] } }"') do set "TUNNEL_TOKEN=%%i"
REM Если не нашли в .env, пробуем переменную окружения (старый вариант)
if "%TUNNEL_TOKEN%"=="" set "TUNNEL_TOKEN=%CLOUDFLARE_TUNNEL_TOKEN%"
if "%TUNNEL_TOKEN%"=="" (
    echo WARNING: CLOUDFLARED_TUNNEL_TOKEN not found in .env or environment.
    echo Skipping Cloudflare Tunnel startup.
) else (
    REM /k чтобы видеть ошибки туннеля
    start "cloudflared" /D "%ROOT%" cmd /k cloudflared.exe tunnel run --protocol http2 --token "%TUNNEL_TOKEN%"
)

echo.
echo All components started (check separate windows for logs).
echo To stop them, close the corresponding windows or stop the processes.

endlocal

