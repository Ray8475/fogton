# Скрипт запуска бота с cloudflared туннелем (поддерживает HTTPS)
# Автоматически извлекает URL из cloudflared и передаёт его боту

param(
    [string]$CloudflaredPath = "cloudflared.exe",
    [int]$LocalPort = 8081
)

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$BotDir = Join-Path $Root "bot"
$WebhookUrlFile = Join-Path $Root ".webhook_url"

# Проверка наличия cloudflared
$cloudflaredPath = Join-Path $Root $CloudflaredPath
if (-not (Test-Path $cloudflaredPath)) {
    Write-Host "ERROR: cloudflared.exe not found at: $cloudflaredPath" -ForegroundColor Red
    Write-Host "Download from: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads" -ForegroundColor Yellow
    exit 1
}

# Проверка BOT_TOKEN
$env:BOT_TOKEN = [System.Environment]::GetEnvironmentVariable("BOT_TOKEN", "Process")
if (-not $env:BOT_TOKEN) {
    $envFile = Join-Path $Root ".env"
    if (Test-Path $envFile) {
        Get-Content $envFile | ForEach-Object {
            if ($_ -match '^\s*BOT_TOKEN\s*=\s*(.+)$') {
                $env:BOT_TOKEN = $matches[1].Trim()
            }
        }
    }
    if (-not $env:BOT_TOKEN) {
        Write-Host "ERROR: BOT_TOKEN not set. Set it in .env or environment variable." -ForegroundColor Red
        exit 1
    }
}

Write-Host "Starting cloudflared tunnel on port $LocalPort..." -ForegroundColor Cyan

# Запуск cloudflared в фоне с перехватом вывода
# Cloudflared может выводить URL в stderr, поэтому перехватываем оба потока
$outputFile = "$env:TEMP\cloudflared_output.txt"
$errorFile = "$env:TEMP\cloudflared_error.txt"

$cloudflaredProcess = Start-Process -FilePath $cloudflaredPath -ArgumentList @(
    "tunnel", "--url", "http://localhost:$LocalPort"
) -NoNewWindow -PassThru -RedirectStandardOutput $outputFile -RedirectStandardError $errorFile

Start-Sleep -Seconds 3

# Функция для извлечения URL из вывода cloudflared
function Extract-CloudflaredUrl {
    param([string]$Output)
    
    # Формат вывода cloudflared может быть разным:
    # "https://xxxx-xxxx-xxxx.trycloudflare.com"
    # "https://xxxx.trycloudflare.com"
    # Может быть в разных строках, может быть с префиксами
    
    $url = $null
    
    # Паттерн 1: полный HTTPS URL от cloudflare
    if ($Output -match '(https://[a-zA-Z0-9\-]+\.trycloudflare\.com)') {
        $url = $matches[1]
    }
    
    # Паттерн 2: только домен без протокола
    if (-not $url -and $Output -match '([a-zA-Z0-9\-]+\.trycloudflare\.com)') {
        $url = "https://$($matches[1])"
    }
    
    return $url
}

# Функция для чтения обоих потоков
function Read-CloudflaredOutput {
    $combined = ""
    
    if (Test-Path $outputFile) {
        $stdout = Get-Content $outputFile -Raw -ErrorAction SilentlyContinue
        if ($stdout) {
            $combined += $stdout
        }
    }
    
    if (Test-Path $errorFile) {
        $stderr = Get-Content $errorFile -Raw -ErrorAction SilentlyContinue
        if ($stderr) {
            $combined += "`n$stderr"
        }
    }
    
    return $combined
}

# Мониторинг вывода cloudflared для извлечения URL
$webhookUrl = $null
$maxWaitTime = 30
$waited = 0

Write-Host "Waiting for cloudflared to provide public URL..." -ForegroundColor Yellow
Write-Host "Checking both stdout and stderr streams..." -ForegroundColor Gray

while (-not $webhookUrl -and $waited -lt $maxWaitTime) {
    Start-Sleep -Seconds 1
    $waited++
    
    # Читаем оба потока
    $cloudflaredOutput = Read-CloudflaredOutput
    
    if ($cloudflaredOutput) {
        # Отладочный вывод каждые 3 секунды
        if ($waited % 3 -eq 0) {
            Write-Host "[$waited s] Checking output..." -ForegroundColor Gray
            if ($waited -le 6) {
                Write-Host "Output preview:" -ForegroundColor Gray
                $preview = $cloudflaredOutput.Substring(0, [Math]::Min(200, $cloudflaredOutput.Length))
                Write-Host $preview -ForegroundColor Gray
            }
        }
        
        $webhookUrl = Extract-CloudflaredUrl -Output $cloudflaredOutput
        if ($webhookUrl) {
            Write-Host "Found cloudflared URL: $webhookUrl" -ForegroundColor Green
            break
        }
    }
    
    # Проверка, что процесс ещё работает
    if ($cloudflaredProcess.HasExited) {
        Write-Host "ERROR: cloudflared process exited unexpectedly" -ForegroundColor Red
        Write-Host "Exit code: $($cloudflaredProcess.ExitCode)" -ForegroundColor Red
        
        Write-Host "`nSTDOUT:" -ForegroundColor Yellow
        if (Test-Path $outputFile) {
            Get-Content $outputFile | Write-Host
        } else {
            Write-Host "(empty)" -ForegroundColor Gray
        }
        
        Write-Host "`nSTDERR:" -ForegroundColor Yellow
        if (Test-Path $errorFile) {
            Get-Content $errorFile | Write-Host
        } else {
            Write-Host "(empty)" -ForegroundColor Gray
        }
        
        exit 1
    }
}

if (-not $webhookUrl) {
    Write-Host "ERROR: Could not extract URL from cloudflared output after $maxWaitTime seconds" -ForegroundColor Red
    Write-Host ""
    Write-Host "STDOUT:" -ForegroundColor Yellow
    if (Test-Path $outputFile) {
        $stdoutContent = Get-Content $outputFile -Raw -ErrorAction SilentlyContinue
        if ($stdoutContent) {
            Write-Host $stdoutContent
        } else {
            Write-Host "(empty)" -ForegroundColor Gray
        }
    } else {
        Write-Host "(file not found)" -ForegroundColor Gray
    }
    
    Write-Host ""
    Write-Host "STDERR:" -ForegroundColor Yellow
    if (Test-Path $errorFile) {
        $stderrContent = Get-Content $errorFile -Raw -ErrorAction SilentlyContinue
        if ($stderrContent) {
            Write-Host $stderrContent
        } else {
            Write-Host "(empty)" -ForegroundColor Gray
        }
    } else {
        Write-Host "(file not found)" -ForegroundColor Gray
    }
    
    Write-Host ""
    Write-Host "Process status:" -ForegroundColor Yellow
    Write-Host "  HasExited: $($cloudflaredProcess.HasExited)" -ForegroundColor Gray
    if ($cloudflaredProcess.HasExited) {
        Write-Host "  ExitCode: $($cloudflaredProcess.ExitCode)" -ForegroundColor Gray
    }
    
    Stop-Process -Id $cloudflaredProcess.Id -Force -ErrorAction SilentlyContinue
    exit 1
}

# Сохраняем URL в файл для бота
$webhookUrl | Out-File -FilePath $WebhookUrlFile -Encoding utf8 -NoNewline -Force
Write-Host ""
Write-Host "Webhook URL saved: $webhookUrl" -ForegroundColor Green
Write-Host "Full webhook URL: $webhookUrl/telegram/webhook" -ForegroundColor Cyan
Write-Host ""

# Устанавливаем переменные окружения для бота
# НЕ устанавливаем WEBHOOK_BASE_URL, чтобы бот использовал файл вместо переменной окружения
# Это позволяет динамически обновлять URL из файла
# Удаляем переменную окружения, если она была установлена ранее
if (Test-Path Env:WEBHOOK_BASE_URL) {
    Remove-Item Env:WEBHOOK_BASE_URL
    Write-Host "Removed WEBHOOK_BASE_URL from environment (using file instead)" -ForegroundColor Gray
}
$env:BOT_MODE = "webhook"
$env:WEBHOOK_URL_FILE = $WebhookUrlFile

# Фоновая задача для мониторинга cloudflared
$monitorCloudflaredScript = {
    param($CloudflaredProcessId, $ErrorFile)
    
    while ($true) {
        Start-Sleep -Seconds 5
        
        # Проверка, что cloudflared ещё работает
        try {
            $proc = Get-Process -Id $CloudflaredProcessId -ErrorAction Stop
        } catch {
            Write-Host "[$(Get-Date -Format 'HH:mm:ss')] ERROR: cloudflared process died!" -ForegroundColor Red
            break
        }
        
        # Проверка на ошибки в stderr
        if (Test-Path $ErrorFile) {
            $errorContent = Get-Content $ErrorFile -Raw -ErrorAction SilentlyContinue
            if ($errorContent -and $errorContent -match '530|unregistered|error|failed') {
                Write-Host "[$(Get-Date -Format 'HH:mm:ss')] WARNING: cloudflared error detected:" -ForegroundColor Yellow
                Write-Host $errorContent -ForegroundColor Yellow
            }
        }
    }
}

# Запуск монитора cloudflared в фоне
$monitorJob = Start-Job -ScriptBlock $monitorCloudflaredScript -ArgumentList @(
    $cloudflaredProcess.Id,
    "$env:TEMP\cloudflared_error.txt"
)

# Запуск бота
Write-Host "Starting bot..." -ForegroundColor Cyan
Write-Host "Press Ctrl+C to stop both cloudflared and bot" -ForegroundColor Yellow
Write-Host ""
Write-Host "NOTE: If you see '530 The origin has been unregistered', cloudflared tunnel disconnected." -ForegroundColor Yellow
Write-Host "      Restart the script to reconnect." -ForegroundColor Yellow
Write-Host ""

try {
    Push-Location $BotDir
    python -m app.main
} finally {
    Pop-Location
    Stop-Job -Job $monitorJob -ErrorAction SilentlyContinue
    Remove-Job -Job $monitorJob -ErrorAction SilentlyContinue
    Stop-Process -Id $cloudflaredProcess.Id -Force -ErrorAction SilentlyContinue
    Write-Host ""
    Write-Host "Stopped cloudflared tunnel and bot" -ForegroundColor Yellow
}
