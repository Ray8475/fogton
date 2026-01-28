from __future__ import annotations

import os
import asyncio

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from dotenv import load_dotenv


load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
WEBHOOK_BASE_URL = os.getenv("WEBHOOK_BASE_URL", "")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")
WEBAPP_URL = os.getenv("WEBAPP_URL", "")
BOT_MODE = os.getenv("BOT_MODE", "").lower()  # "polling" | "webhook" | ""

WEBHOOK_PATH = "/telegram/webhook"
WEBHOOK_URL = f"{WEBHOOK_BASE_URL}{WEBHOOK_PATH}"


bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


@dp.message(CommandStart())
async def cmd_start(message: Message):
    kb = None
    if WEBAPP_URL:
        kb = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="Открыть приложение", url=WEBAPP_URL)]]
        )
    await message.answer("Привет! Это MVP Gifts Futures. Открой Mini App:", reply_markup=kb)


async def run_polling() -> None:
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


async def run_webhook() -> None:
    if not WEBHOOK_BASE_URL:
        raise SystemExit("WEBHOOK_BASE_URL is required for webhook mode")

    await bot.set_webhook(
        WEBHOOK_URL,
        secret_token=WEBHOOK_SECRET or None,
        drop_pending_updates=True,
    )

    app = web.Application()
    SimpleRequestHandler(dispatcher=dp, bot=bot, secret_token=WEBHOOK_SECRET or None).register(
        app, path=WEBHOOK_PATH
    )
    setup_application(app, dp, bot=bot)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=8081)
    await site.start()

    # run forever
    await asyncio.Event().wait()


if __name__ == "__main__":
    if not BOT_TOKEN:
        raise SystemExit("BOT_TOKEN is required")

    use_webhook = BOT_MODE == "webhook" or (BOT_MODE == "" and bool(WEBHOOK_BASE_URL))
    if use_webhook:
        asyncio.run(run_webhook())
    else:
        asyncio.run(run_polling())

