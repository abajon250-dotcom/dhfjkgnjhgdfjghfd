import asyncio
import logging
import sys
import os
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from database import init_db
from handlers import start

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")

async def main():
    if not TOKEN:
        print("❌ Ошибка: BOT_TOKEN не найден в переменных окружения!")
        return

    init_db()
    print("✅ База данных инициализирована.")

    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN))
    dp = Dispatcher()

    dp.include_router(start.router)

    print("🚀 Бот Aegis VK запущен и готов к работе!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("🛑 Бот остановлен.")
