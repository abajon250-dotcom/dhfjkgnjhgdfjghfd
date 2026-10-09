from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def get_main_keyboard(is_admin: bool = False):
    keyboard = [
        [KeyboardButton(text="🔑 Добавить VK аккаунт"), KeyboardButton(text="📋 Мои аккаунты")],
        [KeyboardButton(text="💎 Купить подписку"), KeyboardButton(text="👤 Профиль")]
    ]
    if is_admin:
        keyboard.append([KeyboardButton(text="🛠 Админ-панель")])
        
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def get_cancel_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Отмена")]],
        resize_keyboard=True
    )
