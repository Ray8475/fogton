# Устранение проблем с cloudflared

## Ошибка 502: "Bad Gateway - An error occurred while opening a stream to the origin"

Эта ошибка означает, что cloudflared получил запрос, но не смог подключиться к боту на localhost:8081.

**Причина:** Бот вызывал `set_webhook()` до того, как начинал слушать порт 8081. Telegram сразу после регистрации webhook шлёт запрос на ваш URL, и туннель пытался проксировать его на порт, который ещё не слушал.

**Исправление:** В коде бота порядок изменён: сначала поднимается HTTP-сервер на порту 8081, затем вызывается `set_webhook()`. После обновления кода перезапустите скрипт:

```powershell
.\run-bot-with-cloudflared.ps1
```

Если 502 всё ещё появляется:
- Убедитесь, что порт 8081 не занят другим процессом: `netstat -ano | findstr :8081`
- Перезапустите скрипт и подождите 2–3 секунды после сообщения "Listening on port 8081" перед действиями в боте

---

## Ошибка 530: "The origin has been unregistered from Argo Tunnel"

Эта ошибка означает, что туннель cloudflared отключился. Возможные причины:

1. **Туннель закрылся** - cloudflared процесс завершился
2. **Проблемы с сетью** - потеряно соединение с серверами Cloudflare
3. **Таймаут** - туннель был неактивен слишком долго

### Решение

1. **Перезапустите скрипт:**
   ```powershell
   .\run-bot-with-cloudflared.ps1
   ```

2. **Проверьте, что порт 8081 свободен:**
   ```powershell
   netstat -ano | findstr :8081
   ```
   Если порт занят, завершите процесс, который его использует.

3. **Проверьте логи cloudflared:**
   - Файлы находятся в `%TEMP%\cloudflared_output.txt` и `%TEMP%\cloudflared_error.txt`
   - Или запустите cloudflared вручную для отладки:
     ```powershell
     .\cloudflared.exe tunnel --url http://localhost:8081
     ```

## Альтернативные решения

### Использовать ngrok

Если cloudflared нестабилен, можно использовать ngrok:

1. Установите ngrok: https://ngrok.com/download
2. Запустите туннель:
   ```powershell
   ngrok http 8081
   ```
3. Скопируйте HTTPS URL из вывода ngrok
4. Сохраните его в файл `.webhook_url`:
   ```powershell
   "https://xxxx-xxxx-xxxx.ngrok-free.app" | Out-File -FilePath .webhook_url -Encoding utf8 -NoNewline
   ```
5. Запустите бота вручную:
   ```powershell
   cd bot
   $env:BOT_MODE = "webhook"
   python -m app.main
   ```

### Использовать localtunnel

1. Установите localtunnel:
   ```powershell
   npm install -g localtunnel
   ```
2. Запустите туннель:
   ```powershell
   lt --port 8081
   ```
3. Используйте полученный HTTPS URL аналогично ngrok

## Профилактика

- **Стабильное интернет-соединение** - убедитесь, что соединение стабильно
- **Мониторинг процесса** - скрипт теперь мониторит состояние cloudflared
- **Автоматический перезапуск** - можно добавить в systemd/supervisor для автоматического перезапуска

## Дополнительная информация

- Cloudflared документация: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/
- TryCloudflare (быстрые туннели): https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/do-more-with-tunnels/trycloudflare/
