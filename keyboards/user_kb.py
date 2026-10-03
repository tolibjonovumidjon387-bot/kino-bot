"""
Foydalanuvchi klaviaturalari
"""
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder
from config import CATEGORIES, PAGE_SIZE
from database.models import Movie, RequiredChannel


def main_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🎬 Kategoriyalar"), KeyboardButton(text="🔍 Kino kodi")],
            [KeyboardButton(text="📩 Admin bilan bog'lanish")],
        ],
        resize_keyboard=True,
    )


def categories_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for cat in CATEGORIES:
        builder.button(text=cat, callback_data=f"cat:{cat}")
    builder.adjust(1)
    return builder.as_markup()


def movies_list_kb(
    movies: list[Movie],
    category: str,
    page: int,
    total: int,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    for movie in movies:
        builder.button(
            text=f"🎬 {movie.title} [{movie.code}]",
            callback_data=f"get_movie:{movie.code}",
        )

    # Sahifalash tugmalari
    nav_buttons = []
    if page > 0:
        nav_buttons.append(
            InlineKeyboardButton(text="⬅️ Oldingi", callback_data=f"cat_page:{category}:{page - 1}")
        )
    total_pages = (total - 1) // PAGE_SIZE + 1
    nav_buttons.append(
        InlineKeyboardButton(text=f"📄 {page + 1}/{total_pages}", callback_data="noop")
    )
    if (page + 1) * PAGE_SIZE < total:
        nav_buttons.append(
            InlineKeyboardButton(text="Keyingi ➡️", callback_data=f"cat_page:{category}:{page + 1}")
        )

    builder.adjust(1)
    if nav_buttons:
        builder.row(*nav_buttons)

    builder.row(InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_categories"))
    return builder.as_markup()


def subscription_check_kb(channels: list[RequiredChannel]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for ch in channels:
        builder.button(
            text=f"📢 {ch.channel_title or 'Kanal'}",
            url=ch.invite_link,
        )
    builder.button(text="✅ Obunani tekshirish", callback_data="check_subscription")
    builder.adjust(1)
    return builder.as_markup()
