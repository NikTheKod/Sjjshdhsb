from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

STARS_OPTIONS = [
    50, 75, 100, 150, 250, 350, 500, 750,
    1000, 1500, 2500, 5000, 10000, 25000, 35000,
    50000, 100000, 150000, 500000, 1000000
]

def get_stars_keyboard():
    builder = InlineKeyboardBuilder()
    for stars in STARS_OPTIONS:
        builder.button(text=f"⭐️ {stars:,} Stars", callback_data=f"select_{stars}")
    builder.adjust(2)
    return builder.as_markup()

def get_main_menu():
    builder = InlineKeyboardBuilder()
    builder.button(text="⭐️ Купить Stars", callback_data="menu_buy")
    builder.button(text="📢 Канал", url="https://t.me/your_channel")
    builder.button(text="🆘 Поддержка", url="https://t.me/your_support")
    builder.adjust(1)
    return builder.as_markup()

def get_admin_menu():
    builder = InlineKeyboardBuilder()
    builder.button(text="📊 Статистика", callback_data="admin_stats")
    builder.button(text="💰 Ручная выдача Stars", callback_data="admin_manual")
    builder.button(text="📋 Список покупок", callback_data="admin_orders")
    builder.button(text="🔄 Обновить", callback_data="admin_refresh")
    builder.adjust(1)
    return builder.as_markup()

def get_confirm_keyboard(purchase_id):
    builder = InlineKeyboardBuilder()
    builder.button(text="💳 Оплатить платеж", callback_data=f"pay_{purchase_id}")
    builder.button(text="🔙 Отмена", callback_data="menu_buy")
    builder.adjust(1)
    return builder.as_markup()
