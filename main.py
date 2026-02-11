import os
import asyncio
import random
from datetime import datetime, date
from typing import Optional

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
import asyncpg
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# === Конфигурация ===
TOKEN = os.getenv("TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

# Колода Таро (название и короткое описание)
TAROT_DECK = {
    "Шут": "Новое начало, спонтанность, свобода от ожиданий.",
    "Маг": "Сила воли, мастерство, проявление идей в реальность.",
    "Верховная Жрица": "Интуиция, тайные знания, внутренний голос.",
    "Императрица": "Изобилие, плодородие, связь с природой.",
    "Император": "Власть, структура, контроль, отцовская фигура.",
    "Влюбленные": "Выбор, союз, отношения, сердечные связи.",
    "Колесо Фортуны": "Судьба, перемены, поворотный момент.",
    "Смерть": "Трансформация, завершение, освобождение от старого.",
    "Башня": "Внезапное разрушение, прорыв, крушение иллюзий.",
    "Луна": "Иллюзии, подсознание, скрытые страхи, интуиция.",
    "Солнце": "Успех, радость, ясность, жизненная сила.",
    "Мир": "Завершение, целостность, гармония, награда."
}

# === База данных ===
async def create_pool():
    """Создает пул соединений с PostgreSQL."""
    return await asyncpg.create_pool(DATABASE_URL)

async def init_db(pool):
    """Инициализирует таблицу пользователей при первом запуске."""
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                last_free DATE
            );
        """)
        print("✅ База данных инициализирована")

async def get_user_last_free(pool, user_id: int) -> Optional[date]:
    """Получает дату последнего бесплатного расклада пользователя."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT last_free FROM users WHERE user_id = $1",
            user_id
        )
        return row['last_free'] if row else None

async def update_user_last_free(pool, user_id: int):
    """Обновляет дату последнего бесплатного расклада."""
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO users (user_id, last_free)
            VALUES ($1, $2)
            ON CONFLICT (user_id) 
            DO UPDATE SET last_free = $2
        """, user_id, date.today())

# === FSM для Pro-расклада ===
class ProForm(StatesGroup):
    waiting_for_question = State()

# === Инициализация бота ===
bot = Bot(token=TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
pool = None  # Будет инициализирован при старте

# === Клавиатуры ===
def main_menu_keyboard():
    """Главное меню с выбором расклада."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔮 Бесплатный расклад", callback_data="free")],
        [InlineKeyboardButton(text="💎 PRO расклад", callback_data="pro")]
    ])
    return keyboard

def back_to_menu_keyboard():
    """Кнопка возврата в меню."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 В меню", callback_data="menu")]
    ])
    return keyboard

# === Генераторы раскладов ===
def get_free_spread():
    """Генерирует бесплатный расклад: случайная карта + короткое описание."""
    card = random.choice(list(TAROT_DECK.keys()))
    description = TAROT_DECK[card]
    
    # Мистические фразы для бесплатного расклада
    mystical_phrases = [
        f"🔮 **{card}**",
        f"✨ **{card}**",
        f"🌙 **{card}**",
        f"⭐ **{card}**"
    ]
    
    intro = random.choice(mystical_phrases)
    
    templates = [
        f"{intro}\n\n{description}\n\n"
        f"Это лишь намёк, тень грядущего. Полный разбор доступен в PRO версии 💎",
        
        f"{intro}\n\n{description}\n\n"
        f"Твоё подсознание уловило послание. PRO расклад раскроет все тайны этой карты. 💎",
        
        f"{intro}\n\n{description}\n\n"
        f"Это первая глава твоей истории. Узнай продолжение с PRO разбором. 💎"
    ]
    
    return random.choice(templates)

def get_pro_spread(card: str, question: str) -> str:
    """Генерирует PRO расклад с учётом вопроса пользователя."""
    description = TAROT_DECK[card]
    
    # PRO расклады — более глубокие, персонализированные
    pro_templates = [
        f"💎 **{card}**\n\n"
        f"Твой вопрос: _{question}_\n\n"
        f"{description}\n\n"
        f"Эта карта указывает на скрытые энергии вокруг твоей ситуации. "
        f"Ты находишься в точке выбора, даже если сейчас этого не ощущаешь. "
        f"Твоё беспокойство — это компас. Прислушайся к тому, что ты на самом деле хочешь.\n\n"
        f"✨ *Ответ уже близко, но тебе нужно сделать шаг в неизвестность.*",
        
        f"💎 **{card}**\n\n"
        f"Ты спросил(а): _{question}_\n\n"
        f"{description}\n\n"
        f"В твоём вопросе скрыто больше, чем кажется. Ты ищешь не просто ответ, "
        f"а подтверждение тому, что уже знаешь внутри. "
        f"Эта карта говорит: ты готова(ов) к переменам, даже если они пугают.\n\n"
        f"🌙 *Доверься своей интуиции.*",
        
        f"💎 **{card}**\n\n"
        f"Твой запрос: _{question}_\n\n"
        f"{description}\n\n"
        f"Заметь: ты обратился(ась) к картам именно с этим вопросом сегодня. Совпадений не бывает. "
        f"В твоей жизни назревает важный сдвиг. Эта карта — не приговор, а совет. "
        f"Она показывает твой потенциал в данной ситуации.\n\n"
        f"⭐ *Вселенная говорит с тобой через символы.*"
    ]
    
    return random.choice(pro_templates)

# === Обработчики команд ===
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    """Обработчик команды /start."""
    user_name = message.from_user.first_name
    
    welcome_text = (
        f"✨ Привет, {user_name}!\n\n"
        f"Я — мистический проводник в мир Таро. "
        f"Тени прошлого, тайны настоящего и намёки на будущее — "
        f"всё это хранят древние карты.\n\n"
        f"Выбери свой расклад:"
    )
    
    await message.answer(welcome_text, reply_markup=main_menu_keyboard())

@dp.callback_query(lambda c: c.data == "menu")
async def callback_menu(callback: CallbackQuery):
    """Возврат в главное меню."""
    await callback.message.edit_text(
        "🔮 Выбери расклад:",
        reply_markup=main_menu_keyboard()
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data == "free")
async def callback_free(callback: CallbackQuery):
    """Обработчик бесплатного расклада с проверкой лимита."""
    user_id = callback.from_user.id
    
    # Проверяем, делал ли пользователь бесплатный расклад сегодня
    last_free = await get_user_last_free(pool, user_id)
    
    if last_free == date.today():
        await callback.message.edit_text(
            "❌ Сегодня ты уже получал(а) бесплатный расклад.\n"
            "Возвращайся завтра или попробуй 💎 PRO версию — без ограничений!",
            reply_markup=back_to_menu_keyboard()
        )
        await callback.answer()
        return
    
    # Генерируем расклад
    spread = get_free_spread()
    
    # Обновляем дату последнего обращения
    await update_user_last_free(pool, user_id)
    
    await callback.message.edit_text(
        spread,
        reply_markup=back_to_menu_keyboard(),
        parse_mode="Markdown"
    )
    await callback.answer("🔮 Карта выбрана...")

@dp.callback_query(lambda c: c.data == "pro")
async def callback_pro(callback: CallbackQuery, state: FSMContext):
    """Начало PRO расклада — запрос вопроса."""
    await callback.message.edit_text(
        "💎 **PRO расклад**\n\n"
        "Напиши одним сообщением, что тебя волнует сегодня.\n"
        "Это может быть вопрос о отношениях, карьере, саморазвитии "
        "или просто запрос «что мне сейчас важно знать».\n\n"
        "_Я вытяну карту и дам глубокий разбор специально под твой запрос._",
        parse_mode="Markdown"
    )
    await state.set_state(ProForm.waiting_for_question)
    await callback.answer()

@dp.message(ProForm.waiting_for_question)
async def process_pro_question(message: types.Message, state: FSMContext):
    """Обрабатывает вопрос пользователя и даёт PRO расклад."""
    question = message.text
    
    # Ограничим длину вопроса для красоты ответа
    if len(question) > 150:
        question = question[:150] + "..."
    
    # Выбираем случайную карту
    card = random.choice(list(TAROT_DECK.keys()))
    
    # Генерируем PRO расклад
    pro_response = get_pro_spread(card, question)
    
    # Отправляем ответ
    await message.answer(
        pro_response,
        reply_markup=back_to_menu_keyboard(),
        parse_mode="Markdown"
    )
    
    # Завершаем состояние
    await state.clear()

async def on_startup():
    """Действия при запуске бота."""
    global pool
    print("🚀 Запуск бота...")
    try:
        pool = await create_pool()
        await init_db(pool)
        print("✅ Бот готов к работе!")
    except Exception as e:
        print(f"❌ Ошибка при запуске: {e}")
        raise

async def on_shutdown():
    """Действия при остановке бота."""
    print("🛑 Остановка бота...")
    if pool:
        await pool.close()
    await bot.session.close()
    print("✅ Бот остановлен")

async def main():
    """Главная функция запуска."""
    await on_startup()
    try:
        await dp.start_polling(bot)
    finally:
        await on_shutdown()

if __name__ == "__main__":
    asyncio.run(main())
