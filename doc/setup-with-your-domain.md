# Настройка с вашим доменом

Когда у вас есть домен, можно получить **постоянные HTTPS-адреса** для бота (webhook) и Mini App.

---

## Вариант 0: Только домен, без Cloudflare и bore

**Да, можно обойтись одним доменом — без туннелей.** Нужно только, чтобы бот и API работали на **сервере с белым IP** (VPS, выделенный сервер и т.п.), а домен был привязан к этому серверу.

### Когда это подходит

- Есть арендованный сервер (VPS) с белым IP.
- Домен указывает на этот сервер (A-запись или CNAME).
- На сервере поднят HTTPS (nginx + Let's Encrypt или аналог) и за ним — бот на порту 8081 (и при необходимости API на 8000).

Тогда **Cloudflare Tunnel и bore не нужны**: запросы идут напрямую на ваш сервер по домену.

### Что сделать

1. **Аренидовать VPS** (любой провайдер: Timeweb, Selectel, DigitalOcean, и т.д.).

2. **Настроить DNS у регистратора домена:**
   - A-запись: `ваш-домен.com` → IP вашего VPS  
   - или поддомен: `bot.ваш-домен.com` → IP VPS.

3. **На сервере:**
   - Установить Python 3.12, склонировать проект, поставить зависимости.
   - Установить nginx (или аналог) и получить SSL-сертификат (Let's Encrypt).
   - Настроить nginx: принять HTTPS на 443 и проксировать на `localhost:8081` (бот) и при необходимости на `localhost:8000` (API).
   - Запустить бота и API (через systemd, supervisor или вручную).

4. **В `.env` на сервере:**
   ```env
   WEBHOOK_BASE_URL=https://bot.ваш-домен.com
   BOT_MODE=webhook
   WEBAPP_URL=https://app.ваш-домен.com
   ```
   (подставьте свои домен/поддомены.)

5. **Mini App** можно раздавать с того же сервера (статика на 5500 или через nginx) или выложить на GitHub Pages и в `WEBAPP_URL` указать URL Pages.

Итог: **домен → DNS → VPS с nginx + SSL → бот и API**. Никаких туннелей.

Подробнее про деплой на VPS — в [deploy-github.md](deploy-github.md).

---

## Вариант 1: Cloudflare Tunnel с вашим доменом

Подходит, если приложение **пока крутится у вас на ПК** (нет своего сервера). Туннель «пробрасывает» интернет на ваш localhost. Домен должен быть добавлен в Cloudflare.

### Шаг 1. Добавить домен в Cloudflare

1. Зайдите на [dash.cloudflare.com](https://dash.cloudflare.com).
2. **Add a site** → введите ваш домен (например `example.com`).
3. Следуйте подсказкам: обновите NS-записи у регистратора на те, что даст Cloudflare.

### Шаг 2. Создать туннель в Zero Trust

1. Откройте [one.dash.cloudflare.com](https://one.dash.cloudflare.com) (или **Zero Trust** в меню Cloudflare).
2. **Networks** → **Tunnels** → **Create a tunnel**.
3. Выберите **Cloudflared** → **Next**.
4. Имя туннеля, например `gifts-bot` → **Save tunnel**.

### Шаг 3. Установить коннектор и получить команду

1. На странице туннеля в блоке **Install connector** выберите ОС (Windows).
2. Скопируйте команду вида:
   ```bash
   cloudflared tunnel run --token <ваш-токен>
   ```
3. На ПК в папке с `cloudflared.exe` (или в PATH) выполните эту команду. Окно не закрывайте — туннель должен быть в статусе **Connected**.

### Шаг 4. Настроить публичные адреса (Public Hostname)

В панели туннеля: **Configure** → **Public Hostname** → **Add a public hostname**.

**Для webhook бота (обязательно):**

| Поле           | Значение                    |
|----------------|-----------------------------|
| Subdomain      | `bot` (или `api`, как хотите) |
| Domain         | ваш домен из списка         |
| Service type   | HTTP                        |
| URL            | `localhost:8081`            |

Сохраните. Будет адрес вида: **`https://bot.ваш-домен.com`**.

**Для Mini App (по желанию):**

| Поле           | Значение                    |
|----------------|-----------------------------|
| Subdomain      | `app` или `miniapp`         |
| Domain         | ваш домен                   |
| Service type   | HTTP                        |
| URL            | `localhost:5500`            |

Будет адрес вида: **`https://app.ваш-домен.com`**.

### Шаг 5. Настроить .env

В корне проекта в `.env` укажите постоянные URL:

```env
# Webhook бота (обязательно для webhook-режима)
WEBHOOK_BASE_URL=https://bot.ваш-домен.com
BOT_MODE=webhook

# Mini App (если настроили отдельный hostname)
WEBAPP_URL=https://app.ваш-домен.com
```

Замените `ваш-домен.com`, `bot` и `app` на ваши subdomain и домен.

### Шаг 6. Как запускать

**Вариант A — без скрипта (ручной запуск):**

1. В одном терминале запустите туннель:
   ```powershell
   .\cloudflared.exe tunnel run --token <ваш-токен>
   ```
2. В другом — бота:
   ```powershell
   python run_bot.py
   ```
   Бот возьмёт `WEBHOOK_BASE_URL` из `.env`.

**Вариант B — скрипт с trycloudflare (временный URL):**

Скрипт `run-bot-with-cloudflared.ps1` создаёт **быстрый** туннель (trycloudflare.com), а не именованный. Чтобы использовать **свой домен**, туннель нужно поднимать вручную командой из шага 6 (Вариант A), а бота — как выше. Файл `.webhook_url` при этом не нужен: используется только `WEBHOOK_BASE_URL` из `.env`.

### Итог

- **Webhook:** `https://bot.ваш-домен.com/telegram/webhook` — постоянный, не меняется при перезапуске.
- **Mini App:** `https://app.ваш-домен.com` — если добавили hostname для порта 5500.
- Пока запущены туннель и бот (и при необходимости webapp на 5500), всё доступно по вашему домену.

---

## Вариант 2: Домен на VPS (позже)

Когда перенесёте API и бота на VPS:

1. Укажите A-запись домена на IP сервера (или CNAME на хост провайдера).
2. Настройте nginx (или аналог) с SSL (Let's Encrypt).
3. В `.env` на VPS укажите:
   - `WEBHOOK_BASE_URL=https://ваш-домен.com` (или `https://bot.ваш-домен.com`)
   - `WEBAPP_URL=https://app.ваш-домен.com` или GitHub Pages.

Подробнее — в [deploy-github.md](deploy-github.md) и [vision.md](../vision.md) (раздел Деплой).

---

## Кратко

| Что сделать | Где |
|-------------|-----|
| Добавить домен в Cloudflare | dash.cloudflare.com |
| Создать туннель и установить cloudflared | Zero Trust → Tunnels |
| Добавить Public Hostname для порта 8081 (бот) | Configure → Public Hostname |
| Добавить Public Hostname для 5500 (Mini App) | по желанию |
| Прописать URL в .env | `WEBHOOK_BASE_URL`, `WEBAPP_URL` |
| Запускать туннель и бота | туннель: `cloudflared tunnel run --token ...`, бот: `python run_bot.py` |

После этого бот и приложение работают по вашему домену с постоянными HTTPS-адресами.
