# Запуск бота с автоперезапуском каждые N минут при падении.
# Опционально запускает cloudflared туннель в фоне (если задан CLOUDFLARED_TUNNEL_TOKEN в .env).
# Использование: .\run-bot-retry.ps1
# Остановка: Ctrl+C

param(
    [int]$RetryIntervalMinutes = 5,
    [int]$TunnelStartDelaySeconds = 15
)

$ErrorActionPreference = "Continue"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$EnvFile = Join-Path $Root ".env"

# Загрузка .env
if (Test-Path $EnvFile) {
    Get-Content $EnvFile -Encoding UTF8 | ForEach-Object {
        if ($_ -match '^\s*([^#=]+)\s*=\s*(.*)$') {
            $key = $matches[1].Trim()
            $value = $matches[2].Trim()
            [System.Environment]::SetEnvironmentVariable($key, $value, "Process")
        }
    }
}

$TunnelToken = [System.Environment]::GetEnvironmentVariable("CLOUDFLARED_TUNNEL_TOKEN", "Process")
$cloudflaredProcess = $null

# Поиск cloudflared (PATH или рядом с скриптом)
$cloudflaredExe = $null
foreach ($candidate in @("cloudflared.exe", (Join-Path $Root "cloudflared.exe"))) {
    if ($candidate -eq "cloudflared.exe") {
        $p = Get-Command cloudflared.exe -ErrorAction SilentlyContinue
        if ($p) { $cloudflaredExe = $p.Source; break }
    } else {
        if (Test-Path $candidate) { $cloudflaredExe = $candidate; break }
    }
}

# Запуск туннеля в фоне (если задан токен)
if ($TunnelToken -and $cloudflaredExe) {
    Write-Host "[$(Get-Date -Format 'HH:mm:ss')] Starting cloudflared tunnel in background..." -ForegroundColor Cyan
    $cloudflaredProcess = Start-Process -FilePath $cloudflaredExe -ArgumentList @(
        "tunnel", "run", "--protocol", "http2", "--token", $TunnelToken
    ) -WindowStyle Hidden -PassThru
    Write-Host "[$(Get-Date -Format 'HH:mm:ss')] Tunnel PID: $($cloudflaredProcess.Id). Waiting $TunnelStartDelaySeconds s..." -ForegroundColor Gray
    Start-Sleep -Seconds $TunnelStartDelaySeconds
} elseif ($TunnelToken -and -not $cloudflaredExe) {
    Write-Host "WARNING: CLOUDFLARED_TUNNEL_TOKEN set but cloudflared.exe not found. Start tunnel manually in another window." -ForegroundColor Yellow
} else {
    Write-Host "[$(Get-Date -Format 'HH:mm:ss')] CLOUDFLARED_TUNNEL_TOKEN not set. Start cloudflared manually if using webhook." -ForegroundColor Gray
}

$attempt = 0
while ($true) {
    $attempt++
    Write-Host ""
    Write-Host "[$(Get-Date -Format 'HH:mm:ss')] Attempt #$attempt - Starting bot..." -ForegroundColor Green
    Push-Location $Root
    try {
        & python run_bot.py
        $exitCode = $LASTEXITCODE
    } finally {
        Pop-Location
    }
    Write-Host "[$(Get-Date -Format 'HH:mm:ss')] Bot exited with code $exitCode. Next start in $RetryIntervalMinutes min." -ForegroundColor Yellow
    Start-Sleep -Seconds ($RetryIntervalMinutes * 60)
}

# При Ctrl+C процесс завершится; cloudflared останется в фоне (можно убить вручную по PID или перезагрузкой)
