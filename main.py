import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import Message
from aiogram.fsm.storage.memory import MemoryStorage

from config import config
from database.db import init_db
from keyboards.keyboards import get_main_menu
from handlers.accounts import router as accounts_router
from handlers.broadcast import router as broadcast_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(name)s - %(message)s")

bot = Bot(token=config.bot_token)
dp = Dispatcher(storage=MemoryStorage())

dp.include_router(accounts_router)
dp.include_router(broadcast_router)

@dp.message(CommandStart())
async def start_handler(message: Message):
    if message.from_user.id != config.admin_id:
        await message.answer("⛔ Доступ ограничен только для администратора.")
        return

    await message.answer(
        f"👋 Привет, {message.from_user.first_name}!\n\n"
        "🤖 Это бот для управления аккаунтами и рассылками через Telethon.\n"
        "Используйте кнопки меню ниже для управления.",
        reply_markup=get_main_menu(),
        parse_mode="html"
    )

async def main():
    logging.info("Инициализация базы данных PostgreSQL...")
    await init_db()
    logging.info("База данных готова. Запуск поллинга...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Бот остановлен.")
