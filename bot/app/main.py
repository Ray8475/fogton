"""
Bot: /start и кнопка «Открыть приложение» (tasklist — итерация 1).
vision.md, conventions.md.
"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import Message
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web
from dotenv import load_dotenv

from .logging import setup_logging, get_logger

load_dotenv()
setup_logging()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
WEBAPP_URL = os.getenv("WEBAPP_URL", "")
BOT_MODE = os.getenv("BOT_MODE", "").lower()
# WEBHOOK_BASE_URL читаем позже в get_webhook_url(), чтобы файл имел приоритет
WEBHOOK_BASE_URL_ENV = os.getenv("WEBHOOK_BASE_URL", "").rstrip("/")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")
WEBHOOK_SET_RETRY_SECONDS = int(os.getenv("WEBHOOK_SET_RETRY_SECONDS", "180"))

# Путь к файлу с webhook URL (для динамического обновления через bore)
WEBHOOK_URL_FILE = os.getenv("WEBHOOK_URL_FILE", "")
if not WEBHOOK_URL_FILE:
    # По умолчанию ищем в корне проекта
    root_dir = Path(__file__).parent.parent.parent.parent
    WEBHOOK_URL_FILE = str(root_dir / ".webhook_url")

WEBHOOK_PATH = "/telegram/webhook"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Текущий webhook URL для отслеживания изменений
_current_webhook_url: str | None = None

logger = get_logger("bot.main")


@dp.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await message.answer(
        "Привет! Это MVP Gifts Futures. Открой Mini App:",
    )


async def run_polling() -> None:
    logger.info("Starting bot in polling mode", extra={"event": "polling_started"})
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


def normalize_url(url: str) -> str:
    """Нормализовать URL: убрать двойные протоколы, убедиться что есть https://"""
    if not url:
        return ""
    
    original_url = url
    # Убираем все пробелы и невидимые символы, затем обрезаем слева/справа
    url = "".join(url.split()).rstrip("/")
    
    # Убираем BOM и другие невидимые символы в начале
    url = url.lstrip("\ufeff\u200b\u200c\u200d\ufeff")
    
    # Сначала убираем все двойные протоколы (цикл на случай множественных дублей)
    iterations = 0
    while url.startswith("https://https://") or url.startswith("http://https://") or url.startswith("https://http://"):
        iterations += 1
        if url.startswith("https://https://"):
            url = url.replace("https://https://", "https://", 1)
        elif url.startswith("http://https://"):
            url = url.replace("http://https://", "https://", 1)
        elif url.startswith("https://http://"):
            url = url.replace("https://http://", "https://", 1)
        if iterations > 10:  # Защита от бесконечного цикла
            break
    
    # Проверяем, есть ли уже протокол ПЕРЕД добавлением нового
    # Используем более надёжную проверку
    has_https = url[:8] == "https://"
    has_http = url[:7] == "http://"
    has_protocol = has_https or has_http
    
    # Добавляем https:// только если протокола нет
    if not has_protocol:
        url = f"https://{url}"
    
    # Финальная проверка на двойной протокол (на всякий случай)
    if url.startswith("https://https://"):
        url = url.replace("https://https://", "https://", 1)
    
    return url


def get_webhook_url() -> str:
    """Получить webhook URL из переменной окружения или файла."""
    global _current_webhook_url
    
    # Сначала пробуем прочитать из файла (для динамического обновления)
    if os.path.exists(WEBHOOK_URL_FILE):
        try:
            with open(WEBHOOK_URL_FILE, "r", encoding="utf-8") as f:
                url_from_file = f.read().strip()
            if url_from_file:
                base_url = normalize_url(url_from_file)
                webhook_url = f"{base_url}{WEBHOOK_PATH}"
                
                if webhook_url != _current_webhook_url:
                    _current_webhook_url = webhook_url
                return webhook_url
        except Exception as e:
            print(f"Warning: Could not read webhook URL from file: {e}")
    
    # Fallback на переменную окружения
    if WEBHOOK_BASE_URL_ENV:
        base_url = normalize_url(WEBHOOK_BASE_URL_ENV)
        webhook_url = f"{base_url}{WEBHOOK_PATH}"
        _current_webhook_url = webhook_url
        return webhook_url
    
    return ""


def validate_webhook_url(url: str) -> bool:
    """Проверить, что URL валидный для Telegram webhook."""
    if not url:
        return False
    # Telegram требует HTTPS для webhook
    if not url.startswith("https://"):
        return False
    # Проверка базовой структуры URL
    if len(url) < 10:  # Минимальная длина для валидного URL
        return False
    return True


async def update_webhook_if_changed() -> bool:
    """Обновить webhook, если URL изменился. Возвращает True, если обновление произошло."""
    global _current_webhook_url
    
    new_url = get_webhook_url()
    if not new_url:
        return False
    
    # Валидация URL перед установкой
    if not validate_webhook_url(new_url):
        logger.warning(
            "Invalid webhook URL format",
            extra={"event": "webhook_url_invalid", "webhook_url": new_url},
        )
        return False
    
    if new_url != _current_webhook_url:
        try:
            await bot.set_webhook(
                new_url,
                secret_token=WEBHOOK_SECRET or None,
                drop_pending_updates=False,  # Не сбрасывать апдейты при обновлении
            )
            logger.info(
                "Webhook URL updated",
                extra={"event": "webhook_updated", "webhook_url": new_url},
            )
            _current_webhook_url = new_url
            return True
        except Exception:
            logger.error(
                "Error updating webhook",
                exc_info=True,
                extra={"event": "webhook_update_error", "webhook_url": new_url},
            )
            return False
    
    return False


async def monitor_webhook_url() -> None:
    """Фоновая задача для мониторинга изменений webhook URL."""
    while True:
        await asyncio.sleep(5)  # Проверяем каждые 5 секунд
        await update_webhook_if_changed()


async def run_webhook() -> None:
    webhook_url = get_webhook_url()
    if not webhook_url:
        raise SystemExit("WEBHOOK_BASE_URL is required for webhook mode (set in env or .webhook_url file)")
    
    # Валидация URL перед установкой
    if not validate_webhook_url(webhook_url):
        raise SystemExit(f"Invalid webhook URL format: {webhook_url}. URL must start with https://")
    
    # Сначала поднимаем HTTP-сервер на порту 8081, чтобы cloudflared/туннель могли
    # проксировать запросы (иначе 502 Bad Gateway при первом запросе от Telegram)
    app = web.Application()
    SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
        secret_token=WEBHOOK_SECRET or None,
    ).register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=8081)
    await site.start()
    logger.info(
        "Listening on port 8081 (ready for tunnel)",
        extra={"event": "webhook_server_started"},
    )
    
    # Теперь регистрируем webhook в Telegram — к этому моменту мы уже принимаем запросы
    logger.info(
        "Setting webhook",
        extra={"event": "webhook_set", "webhook_url": webhook_url},
    )

    # Telegram может какое-то время не резолвить домен (кэш DNS/NXDOMAIN на их стороне).
    # В этом случае не падаем, а повторяем set_webhook() каждые N секунд до успеха.
    while True:
        try:
            await bot.set_webhook(
                webhook_url,
                secret_token=WEBHOOK_SECRET or None,
                drop_pending_updates=True,
            )
            logger.info(
                "Bot started with webhook",
                extra={"event": "webhook_set_ok", "webhook_url": webhook_url},
            )
            break
        except Exception as e:
            msg = str(e)
            logger.error(
                "Failed to set webhook, will retry",
                exc_info=True,
                extra={"event": "webhook_set_error", "webhook_url": webhook_url},
            )
            if "Failed to resolve host" in msg or "Name or service not known" in msg:
                await asyncio.sleep(WEBHOOK_SET_RETRY_SECONDS)
                continue
            raise
    
    # Запускаем мониторинг изменений URL в фоне
    monitor_task = asyncio.create_task(monitor_webhook_url())
    
    try:
        await asyncio.Event().wait()
    finally:
        monitor_task.cancel()
        try:
            await monitor_task
        except asyncio.CancelledError:
            pass


if __name__ == "__main__":
    if not BOT_TOKEN:
        raise SystemExit("BOT_TOKEN is required")
    # Проверяем наличие webhook URL в файле или переменной окружения
    webhook_url_check = get_webhook_url() if os.path.exists(WEBHOOK_URL_FILE) or WEBHOOK_BASE_URL_ENV else ""
    use_webhook = BOT_MODE == "webhook" or (BOT_MODE == "" and bool(webhook_url_check))
    if use_webhook:
        asyncio.run(run_webhook())
    else:
        asyncio.run(run_polling())
