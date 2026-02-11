@echo off
setlocal

REM Определяем корень проекта (папка, где лежит этот .bat)
set "ROOT=%~dp0"
REM убираем завершающий обратный слеш
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"

echo Project root: %ROOT%

echo Starting API (uvicorn) on http://0.0.0.0:8000 ...
REM /k чтобы окно не закрывалось сразу при ошибке
start "api" /D "%ROOT%\backend" cmd /k python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

echo Starting bot (run_bot.py) ...
REM /k чтобы видеть traceback, если бот упадёт
start "bot" /D "%ROOT%" cmd /k python run_bot.py

echo Starting Cloudflare Tunnel (cloudflared) ...
if "%CLOUDFLARE_TUNNEL_TOKEN%"=="" (
    echo WARNING: CLOUDFLARE_TUNNEL_TOKEN is not set. Set it in your environment before running this script.
) else (
    REM /k чтобы видеть ошибки туннеля
    start "cloudflared" /D "%ROOT%" cmd /k cloudflared.exe tunnel run --token "%CLOUDFLARE_TUNNEL_TOKEN%"
)

echo.
echo All components started (check separate windows for logs).
echo To stop them, close the corresponding windows or stop the processes.

endlocal

