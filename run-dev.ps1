param(
    [switch]$NoApi,
    [switch]$NoWeb,
    [switch]$NoTunnel,
    [switch]$NoBot
)

# Базовая директория проекта
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$LogsDir = Join-Path $Root "logs"

if (-not (Test-Path $LogsDir)) {
    New-Item -ItemType Directory -Path $LogsDir | Out-Null
}

 # Каждому запуску — отдельная папка с таймстампом
 $RunId = Get-Date -Format "yyyyMMdd-HHmmss"
 $RunDir = Join-Path $LogsDir $RunId
 New-Item -ItemType Directory -Force -Path $RunDir | Out-Null
 Set-Content -Path (Join-Path $LogsDir "latest.txt") -Value $RunId -Encoding ascii

Write-Host "Project root: $Root" -ForegroundColor Cyan
Write-Host "Logs directory: $LogsDir" -ForegroundColor Cyan
Write-Host "This run logs: $RunDir" -ForegroundColor Cyan

if (-not $NoApi) {
    Write-Host "Starting API (uvicorn) in background..." -ForegroundColor Green
    $apiLog = Join-Path $RunDir "api.log"
    $apiErr = Join-Path $RunDir "api.error.log"
    Start-Process python -ArgumentList @(
        "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--timeout-keep-alive", "75"
    ) -WorkingDirectory (Join-Path $Root "backend") `
      -RedirectStandardOutput $apiLog `
      -RedirectStandardError $apiErr `
      -WindowStyle Hidden
}

if (-not $NoWeb) {
    Write-Host "Starting Mini App static server (http.server 5500) in background..." -ForegroundColor Green
    $webLog = Join-Path $RunDir "webapp.log"
    $webErr = Join-Path $RunDir "webapp.error.log"
    Start-Process python -ArgumentList @(
        "-m", "http.server", "5500"
    ) -WorkingDirectory (Join-Path $Root "webapp\public") `
      -RedirectStandardOutput $webLog `
      -RedirectStandardError $webErr `
      -WindowStyle Hidden
}

if (-not $NoTunnel) {
    # Опционально для локальной отладки; продакшен-деплой — через GitHub (см. vision.md)
    Write-Host "Starting tunnel (cloudflared, http://localhost:5500) in background..." -ForegroundColor Green
    $tunnelLog = Join-Path $RunDir "tunnel.log"
    $cloudflaredPath = Join-Path $Root "cloudflared.exe"
    if (-not (Test-Path $cloudflaredPath)) {
        Write-Warning "cloudflared.exe not found at $cloudflaredPath. Tunnel will NOT be started."
    }
    else {
        Start-Process $cloudflaredPath -ArgumentList @(
            "tunnel", "--url", "http://localhost:5500", "--protocol", "http2"
        ) -WorkingDirectory $Root `
          -RedirectStandardOutput $tunnelLog `
          -RedirectStandardError (Join-Path $RunDir "tunnel.error.log") `
          -WindowStyle Hidden
    }
}

if (-not $NoBot) {
    Write-Host "Starting bot (aiogram polling) in background..." -ForegroundColor Green
    $botLog = Join-Path $RunDir "bot.log"
    $botErr = Join-Path $RunDir "bot.error.log"
    Start-Process python -ArgumentList @(
        "app/main.py"
    ) -WorkingDirectory (Join-Path $Root "bot") `
      -RedirectStandardOutput $botLog `
      -RedirectStandardError $botErr `
      -WindowStyle Hidden
}

Write-Host ""
Write-Host "All components started in background." -ForegroundColor Cyan
Write-Host "To watch logs, use for example:" -ForegroundColor Cyan
Write-Host "  Get-Content '$RunDir\api.log' -Wait" -ForegroundColor Yellow
Write-Host "  Get-Content '$RunDir\bot.log' -Wait" -ForegroundColor Yellow
Write-Host "  Get-Content '$RunDir\webapp.log' -Wait" -ForegroundColor Yellow
Write-Host "  Get-Content '$RunDir\tunnel.log' -Wait" -ForegroundColor Yellow


