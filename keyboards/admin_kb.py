"""
Admin panel klaviaturalari
"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from database.models import RequiredChannel, ScheduledMessage


def admin_main_kb(bot_active: bool) -> InlineKeyboardMarkup:
    status_btn = ("⏸ Botni to'xtatish", "admin:stop_bot") if bot_active else ("▶️ Botni ishga tushirish", "admin:start_bot")
    builder = InlineKeyboardBuilder()
    builder.button(text="🎬 Kinolar", callback_data="admin:movies")
    builder.button(text="📢 Majburiy kanallar", callback_data="admin:channels")
    builder.button(text="📨 Xabar yuborish", callback_data="admin:broadcast")
    builder.button(text="📅 Rejalashtirilgan xabarlar", callback_data="admin:schedules")
    builder.button(text="⚙️ Sozlamalar", callback_data="admin:settings")
    builder.button(text=status_btn[0], callback_data=status_btn[1])
    builder.adjust(2, 2, 2)
    return builder.as_markup()


def admin_movies_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Kino qo'shish", callback_data="admin:add_movie")
    builder.button(text="✏️ Kino tahrirlash", callback_data="admin:edit_movie")
    builder.button(text="🗑 Kino o'chirish", callback_data="admin:delete_movie")
    builder.button(text="📋 Kinolar ro'yxati", callback_data="admin:list_movies")
    builder.button(text="🔙 Orqaga", callback_data="admin:back_main")
    builder.adjust(2, 2, 1)
    return builder.as_markup()


def admin_channels_kb(channels: list[RequiredChannel]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for ch in channels:
        builder.button(
            text=f"❌ {ch.channel_title or ch.channel_id}",
            callback_data=f"admin:rm_channel:{ch.channel_id}",
        )
    builder.button(text="➕ Kanal qo'shish", callback_data="admin:add_channel")
    builder.button(text="🔙 Orqaga", callback_data="admin:back_main")
    builder.adjust(1)
    return builder.as_markup()


def admin_broadcast_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="👤 Bitta foydalanuvchi", callback_data="admin:bc_one")
    builder.button(text="👥 Barcha foydalanuvchilar", callback_data="admin:bc_all")
    builder.button(text="🔙 Orqaga", callback_data="admin:back_main")
    builder.adjust(2, 1)
    return builder.as_markup()


def admin_schedule_kb(schedules: list[ScheduledMessage]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for sch in schedules:
        status_icon = {"active": "▶️", "paused": "⏸", "finished": "✅", "cancelled": "❌"}.get(sch.status, "❓")
        builder.button(
            text=f"{status_icon} Jadval #{sch.id}",
            callback_data=f"admin:sch_view:{sch.id}",
        )
    builder.button(text="➕ Yangi jadval", callback_data="admin:sch_new")
    builder.button(text="🔙 Orqaga", callback_data="admin:back_main")
    builder.adjust(1)
    return builder.as_markup()


def schedule_actions_kb(sch: ScheduledMessage) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if sch.status == "active":
        builder.button(text="⏸ Pauza", callback_data=f"admin:sch_pause:{sch.id}")
    elif sch.status == "paused":
        builder.button(text="▶️ Davom ettirish", callback_data=f"admin:sch_resume:{sch.id}")
    if sch.status in ("active", "paused"):
        builder.button(text="❌ Bekor qilish", callback_data=f"admin:sch_cancel:{sch.id}")
    builder.button(text="🔙 Orqaga", callback_data="admin:schedules")
    builder.adjust(2, 1)
    return builder.as_markup()


def admin_settings_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📱 Admin kontaktni o'zgartirish", callback_data="admin:set_contact")
    builder.button(text="📦 Arxiv kanalni o'zgartirish", callback_data="admin:set_archive")
    builder.button(text="🔙 Orqaga", callback_data="admin:back_main")
    builder.adjust(1)
    return builder.as_markup()


def back_kb(callback: str = "admin:back_main") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Orqaga", callback_data=callback)
    return builder.as_markup()


def confirm_kb(yes_cb: str, no_cb: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Ha, tasdiqlash", callback_data=yes_cb)
    builder.button(text="❌ Yo'q, bekor qilish", callback_data=no_cb)
    builder.adjust(2)
    return builder.as_markup()


def cancel_kb(callback: str = "admin:back_main") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🚫 Bekor qilish", callback_data=callback)
    return builder.as_markup()


def bc_user_select_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="👤 Username orqali", callback_data="admin:bc_by_username")
    builder.button(text="🆔 Telegram ID orqali", callback_data="admin:bc_by_id")
    builder.button(text="🔙 Orqaga", callback_data="admin:broadcast")
    builder.adjust(2, 1)
    return builder.as_markup()
