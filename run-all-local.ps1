param(
    [switch]$NoApi,
    [switch]$NoBot,
    [switch]$NoTunnel
)

# Базовая директория проекта
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "Project root: $Root" -ForegroundColor Cyan

if (-not $NoApi) {
    Write-Host "Starting API (uvicorn) on http://0.0.0.0:8000 ..." -ForegroundColor Green
    Start-Process python -ArgumentList @(
        "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--timeout-keep-alive", "75"
    ) -WorkingDirectory (Join-Path $Root "backend")
}

if (-not $NoBot) {
    Write-Host "Starting bot (run_bot.py) ..." -ForegroundColor Green
    Start-Process python -ArgumentList @(
        "run_bot.py"
    ) -WorkingDirectory $Root
}

if (-not $NoTunnel) {
    $token = $env:CLOUDFLARE_TUNNEL_TOKEN
    if (-not $token) {
        Write-Warning "CLOUDFLARE_TUNNEL_TOKEN is not set. Set it in your environment before running this script."
    }
    else {
        Write-Host "Starting Cloudflare Tunnel (cloudflared) ..." -ForegroundColor Green
        Start-Process cloudflared.exe -ArgumentList @(
            "tunnel", "run", "--protocol", "http2", "--token", $token
        ) -WorkingDirectory $Root
    }
}

Write-Host ""
Write-Host "All components started (check separate windows for logs)." -ForegroundColor Cyan
Write-Host "To stop them, close the corresponding windows or stop the processes." -ForegroundColor Cyan

