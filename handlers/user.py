"""
Foydalanuvchi handlerlari:
- /start
- Kategoriyalar
- Kino kodi yuborish
- Obuna tekshirish
- Admin bilan bog'lanish
"""
import logging
from aiogram import Router, F, Bot
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from config import ADMIN_CONTACT, PAGE_SIZE
from database.crud import (
    get_required_channels, get_movie_by_code,
    get_movies_by_category, get_setting, is_bot_active,
)
from database.models import User
from keyboards.user_kb import (
    main_menu_kb, categories_kb, movies_list_kb, subscription_check_kb,
)
from utils.subscription import inspect_subscription, subscription_prompt
from middlewares.subscription import SubscriptionMiddleware
from utils.helpers import forward_movie_to_user, is_admin

logger = logging.getLogger(__name__)
user_router = Router()
user_router.message.middleware(SubscriptionMiddleware())
user_router.callback_query.middleware(SubscriptionMiddleware())

# ──────────────────────────── /start ─────────────────────────────────────── #

@user_router.message(CommandStart())
async def cmd_start(message: Message, session: AsyncSession, bot: Bot):
    # Bot faolligini tekshirish (admin uchun cheklov yo'q)
    if not is_admin(message.from_user.id):
        active = await is_bot_active(session)
        if not active:
            await message.answer("🔒 Bot vaqtincha to'xtatilgan. Keyinroq urinib ko'ring.")
            return

    args = message.text.split()
    deep_code = args[1] if len(args) > 1 else None

    await message.answer(
        f"👋 Salom, <b>{message.from_user.full_name}</b>!\n\n"
        "🎬 Kino botga xush kelibsiz!\n"
        "Kino kodini yuboring yoki kategoriyani tanlang.",
        reply_markup=main_menu_kb(),
        parse_mode="HTML",
    )

    # Deep link orqali kino kodi kelgan bo'lsa
    if deep_code:
        await _send_movie_by_code(message, session, bot, deep_code)


# ──────────────────────── Asosiy menyu tugmalari ─────────────────────────── #

@user_router.message(F.text == "🎬 Kategoriyalar")
async def show_categories(message: Message, session: AsyncSession):
    if not is_admin(message.from_user.id):
        if not await is_bot_active(session):
            await message.answer("🔒 Bot vaqtincha to'xtatilgan.")
            return
    await message.answer("📂 Kategoriyani tanlang:", reply_markup=categories_kb())


@user_router.message(F.text == "🔍 Kino kodi")
async def ask_movie_code(message: Message, session: AsyncSession):
    if not is_admin(message.from_user.id):
        if not await is_bot_active(session):
            await message.answer("🔒 Bot vaqtincha to'xtatilgan.")
            return
    await message.answer(
        "🔍 Kino kodini kiriting:\n"
        "<i>Masalan: <code>001</code></i>",
        parse_mode="HTML",
    )


@user_router.message(F.text == "📩 Admin bilan bog'lanish")
async def contact_admin(message: Message, session: AsyncSession):
    contact = await get_setting(session, "admin_contact", ADMIN_CONTACT)
    if contact:
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="📩 Admin bilan bog'lanish", url=f"https://t.me/{contact}")
        ]])
        await message.answer("📩 Admin bilan bog'lanish:", reply_markup=kb)
    else:
        await message.answer("ℹ️ Hozircha admin kontakti sozlanmagan.")


# ──────────────────────── Kategoriya callback ────────────────────────────── #

@user_router.callback_query(F.data.startswith("cat:"))
async def category_selected(call: CallbackQuery, session: AsyncSession, bot: Bot):
    if not is_admin(call.from_user.id):
        if not await is_bot_active(session):
            await call.answer("🔒 Bot to'xtatilgan.", show_alert=True)
            return

    category = call.data.split(":", 1)[1]
    await _show_movies_page(call, session, bot, category, page=0)


@user_router.callback_query(F.data.startswith("cat_page:"))
async def category_page(call: CallbackQuery, session: AsyncSession, bot: Bot):
    if not is_admin(call.from_user.id):
        if not await is_bot_active(session):
            await call.answer("🔒 Bot to'xtatilgan.", show_alert=True)
            return

    parts = call.data.split(":")
    category = parts[1]
    page = int(parts[2])
    await _show_movies_page(call, session, bot, category, page)


async def _show_movies_page(
    call: CallbackQuery,
    session: AsyncSession,
    bot: Bot,
    category: str,
    page: int,
):
    await call.answer()
    movies, total = await get_movies_by_category(
        session, category, offset=page * PAGE_SIZE, limit=PAGE_SIZE
    )
    if not movies:
        await call.message.edit_text(
            f"📂 <b>{category}</b>\n\n"
            "🚫 Bu kategoriyada hozircha kino mavjud emas.",
            reply_markup=None,
            parse_mode="HTML",
        )
        return

    await call.message.edit_text(
        f"📂 <b>{category}</b>\n"
        f"Jami: {total} ta kino. Birini tanlang:",
        reply_markup=movies_list_kb(movies, category, page, total),
        parse_mode="HTML",
    )


@user_router.callback_query(F.data == "back_to_categories")
async def back_to_categories(call: CallbackQuery):
    await call.answer()
    await call.message.edit_text("📂 Kategoriyani tanlang:", reply_markup=categories_kb())


@user_router.callback_query(F.data == "noop")
async def noop_callback(call: CallbackQuery):
    await call.answer()


# ─────────────────── Kino olish (tugma orqali) ───────────────────────────── #

@user_router.callback_query(F.data.startswith("get_movie:"))
async def get_movie_by_btn(call: CallbackQuery, session: AsyncSession, bot: Bot):
    if not is_admin(call.from_user.id):
        if not await is_bot_active(session):
            await call.answer("🔒 Bot to'xtatilgan.", show_alert=True)
            return

    code = call.data.split(":", 1)[1]
    await call.answer()
    await _send_movie_by_code(call.message, session, bot, code, user_id=call.from_user.id)


# ─────────────────── Kino kodi matni orqali ──────────────────────────────── #

@user_router.message(F.text & ~F.text.startswith("/"))
async def handle_text_code(message: Message, session: AsyncSession, bot: Bot):
    """Har qanday matn → kino kodi sifatida qabul qilinadi."""
    if not is_admin(message.from_user.id):
        if not await is_bot_active(session):
            await message.answer("🔒 Bot vaqtincha to'xtatilgan. Keyinroq urinib ko'ring.")
            return

    code = message.text.strip()
    await _send_movie_by_code(message, session, bot, code)


async def _send_movie_by_code(
    event: Message,
    session: AsyncSession,
    bot: Bot,
    code: str,
    user_id: int | None = None,
):
    """Kino kodini topib foydalanuvchiga yuboradi."""
    _user_id = user_id or event.from_user.id

    # Entry handlers are protected by SubscriptionMiddleware.
    # check_sub_callback calls this only after a fresh successful check.
    movie = await get_movie_by_code(session, code)
    if not movie:
        await event.answer(
            f"❌ <b>{code}</b> kodli kino topilmadi.\n"
            "Kodni to'g'ri kiritganingizni tekshiring.",
            parse_mode="HTML",
        )
        return

    ok, err = await forward_movie_to_user(
        bot=bot,
        user_id=_user_id,
        from_chat_id=movie.channel_id,
        message_id=movie.message_id,
    )
    if ok:
        await event.answer(
            f"✅ <b>{movie.title}</b> kinosi yuborildi!",
            parse_mode="HTML",
        )
        return True
    elif err == "not_found":
        await event.answer(
            "⚠️ Kino topildi, lekin arxiv kanalida xabar mavjud emas.\n"
            "Admin bilan bog'laning."
        )
        logger.error(
            "Movie '%s': arxiv kanalida xabar topilmadi. channel_id=%s, msg_id=%s",
            code, movie.channel_id, movie.message_id,
        )
    elif err == "blocked":
        await event.answer(
            "⚠️ Xabar yuborish mumkin emas — siz botni bloklagan bo'lishingiz mumkin."
        )
    else:
        await event.answer("⚠️ Kino yuborishda xatolik yuz berdi. Keyinroq urinib ko'ring.")
        logger.error("Movie '%s' yuborishda xato: %s", code, err)


# ─────────────────────── Obuna tekshirish callback ───────────────────────── #

@user_router.callback_query(F.data == "check_subscription")
async def check_sub_callback(call: CallbackQuery, session: AsyncSession, bot: Bot):
    if not is_admin(call.from_user.id):
        if not await is_bot_active(session):
            await call.answer("🔒 Bot to'xtatilgan.", show_alert=True)
            return

    # Acknowledge before network checks; results are ordinary messages.
    await call.answer()
    channels = [] if is_admin(call.from_user.id) else await get_required_channels(session)
    missing, unavailable = await inspect_subscription(bot, call.from_user.id, channels)
    if missing or unavailable:
        await call.message.answer(
            subscription_prompt(missing, unavailable),
            reply_markup=subscription_check_kb(missing + unavailable),
        )
        return

    from database.crud import set_setting
    pending_key = f"pending_code:{call.from_user.id}"
    pending_code = await get_setting(session, pending_key)
    await call.message.answer(
        "✅ Obuna tasdiqlandi! Kino kodini yuboring yoki kategoriyani tanlang.",
        reply_markup=main_menu_kb(),
    )
    if pending_code:
        sent = await _send_movie_by_code(
            call.message, session, bot, pending_code, user_id=call.from_user.id
        )
        if sent:
            await set_setting(session, pending_key, "")
            await session.commit()
