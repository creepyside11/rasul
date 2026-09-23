from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

def get_main_menu():
    keyboard = [
        [KeyboardButton(text="📱 Менеджер аккаунтов"), KeyboardButton(text="🚀 Функции")],
        [KeyboardButton(text="📊 Мои рассылки")]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def get_accounts_menu():
    keyboard = [
        [InlineKeyboardButton(text="➕ Добавить аккаунт", callback_data="add_account")],
        [InlineKeyboardButton(text="📋 Список аккаунтов", callback_data="list_accounts")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_functions_menu():
    keyboard = [
        [InlineKeyboardButton(text="📨 Запустить рассылку", callback_data="start_broadcast")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_send_type_kb():
    keyboard = [
        [InlineKeyboardButton(text="🎲 Рандомный (по 1)", callback_data="type_random")],
        [InlineKeyboardButton(text="⚡ Одновременный (во все)", callback_data="type_simultaneous")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_cancel_kb():
    keyboard = [
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_action")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)
