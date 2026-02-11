#!/usr/bin/env python3
"""
Запуск бота одной командой из корня проекта.
Подгружает .env из корня, запускает bot/app/main.py.
"""
from __future__ import annotations

import os
import subprocess
import sys

# корень проекта (где лежит run_bot.py)
ROOT = os.path.dirname(os.path.abspath(__file__))
BOT_DIR = os.path.join(ROOT, "bot")

# подгрузить .env из корня (одна точка конфигурации)
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(ROOT, ".env"))
except ImportError:
    pass

if __name__ == "__main__":
    os.chdir(BOT_DIR)
    sys.path.insert(0, BOT_DIR)
    # запуск как модуль: python -m app.main
    code = subprocess.run(
        [sys.executable, "-m", "app.main"],
        cwd=BOT_DIR,
        env=os.environ.copy(),
    ).returncode
    sys.exit(code)
