import asyncio
import random
import os
from datetime import date
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
import asyncpg

TOKEN = os.getenv("TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

bot = Bot(token=TOKEN)
dp = Dispatcher()

tarot_cards = [
    "Шут", "Маг", "Жрица", "Императрица",
    "Император", "Влюбленные", "Колесо Фортуны",
    "Смерть", "Башня", "Луна", "Солнце", "Мир"
]

keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🔮 Бесплатный расклад")],
        [KeyboardButton(text="💎 PRO расклад")]
    ],
    resize_keyboard=True
)

async def create_pool():
    return await asyncpg.create_pool(DATABASE_URL)

@dp.message(Command("start"))
async def start(message: types.Message):
    async with dp["db"].acquire() as conn:
        await conn.execute("""
            INSERT INTO users (user_id, last_free)
            VALUES ($1, NULL)
            ON CONFLICT (user_id) DO NOTHING
        """, message.from_user.id)

    await message.answer(
        "🔮 Добро пожаловать в AI-Oracle\n\nВыбери расклад:",
        reply_markup=keyboard
    )

@dp.message(lambda message: message.text == "🔮 Бесплатный расклад")
async def free_spread(message: types.Message):
    today = date.today()

    async with dp["db"].acquire() as conn:
        last_free = await conn.fetchval(
            "SELECT last_free FROM users WHERE user_id=$1",
            message.from_user.id
        )

        if last_free == today:
            await message.answer("Сегодня бесплатный расклад уже использован 💎")
            return

        await conn.execute(
            "UPDATE users SET last_free=$1 WHERE user_id=$2",
            today, message.from_user.id
        )

    card = random.choice(tarot_cards)

    await message.answer(
        f"🃏 Твоя карта: {card}\n\n"
        f"Это знак. Но есть скрытая деталь...\n\n"
        f"Полный разбор доступен в PRO версии 💎"
    )

@dp.message(lambda message: message.text == "💎 PRO расклад")
async def pro_spread(message: types.Message):
    await message.answer(
        "💎 PRO расклад раскрывает глубинный анализ ситуации.\n\n"
        "Скоро здесь будет подключена подписка."
    )

async def main():
    dp["db"] = await create_pool()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
