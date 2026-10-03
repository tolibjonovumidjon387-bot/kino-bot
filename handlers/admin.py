"""
Admin panel handlerlari — barcha admin amallari shu faylda.

Tuzilma:
  - /admin  →  asosiy panel
  - Kinolar boshqaruvi (qo'shish / tahrirlash / o'chirish / ro'yxat)
  - Majburiy kanallar
  - Arxiv kanali sozlamasi
  - Admin kontakti sozlamasi
  - Bot holati (to'xtatish / yoqish)
  - Broadcast (bitta / hammaga)
  - Rejalashtirilgan xabarlar
"""
import logging
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from config import ADMIN_IDS, CATEGORIES, PAGE_SIZE
from database import crud
from keyboards.admin_kb import (
    admin_main_kb, admin_movies_kb, admin_channels_kb,
    admin_broadcast_kb, admin_schedule_kb, admin_settings_kb,
    back_kb, confirm_kb, cancel_kb, bc_user_select_kb,
    schedule_actions_kb,
)
from utils.helpers import is_admin, forward_movie_to_user
from utils.subscription import check_bot_channel_rights

logger = logging.getLogger(__name__)
admin_router = Router()


# ──────────────────────── Admin filtr ────────────────────────────────────── #

def admin_only(user_id: int) -> bool:
    return user_id in ADMIN_IDS


# ══════════════════════════════════════════════════════════════════════════════
# FSM holatlari
# ══════════════════════════════════════════════════════════════════════════════

class AddMovieFSM(StatesGroup):
    waiting_forward = State()       # Forward yoki kanal/msg ID
    waiting_code = State()
    waiting_title = State()
    waiting_category = State()
    waiting_channel_msg = State()   # "channel_id:message_id" shaklida
    confirm = State()


class EditMovieFSM(StatesGroup):
    waiting_code = State()
    choose_field = State()
    waiting_value = State()


class DeleteMovieFSM(StatesGroup):
    waiting_code = State()
    confirm = State()


class AddChannelFSM(StatesGroup):
    waiting_channel_id = State()
    waiting_invite_link = State()
    confirm = State()


class BroadcastOneFSM(StatesGroup):
    choose_method = State()
    waiting_identifier = State()
    confirm_user = State()
    waiting_message = State()
    confirm_send = State()


class BroadcastAllFSM(StatesGroup):
    waiting_message = State()
    confirm = State()


class ScheduleFSM(StatesGroup):
    waiting_content = State()
    waiting_recipient = State()
    waiting_start_date = State()
    waiting_time = State()
    waiting_duration = State()
    confirm = State()


class SetContactFSM(StatesGroup):
    waiting_username = State()


class SetArchiveFSM(StatesGroup):
    waiting_channel_id = State()


# ══════════════════════════════════════════════════════════════════════════════
# YORDAMCHI FUNKSIYALAR
# ══════════════════════════════════════════════════════════════════════════════

async def _admin_check(event, session: AsyncSession) -> bool:
    """Admin tekshiruvini o'tkazadi. False bo'lsa xabar yuboradi."""
    uid = event.from_user.id
    if not admin_only(uid):
        if isinstance(event, CallbackQuery):
            await event.answer("🚫 Ruxsat yo'q!", show_alert=True)
        else:
            await event.answer("🚫 Siz admin emassiz.")
        return False
    return True


async def _send_admin_panel(target, session: AsyncSession, text: str = "🛠 Admin panel:"):
    """Admin asosiy menyusini yuboradi."""
    bot_active = await crud.is_bot_active(session)
    users_count = await crud.count_users(session)
    movies_count = await crud.count_movies(session)
    full_text = (
        f"{text}\n\n"
        f"👥 Foydalanuvchilar: <b>{users_count}</b>\n"
        f"🎬 Kinolar: <b>{movies_count}</b>\n"
        + ("🟢 Bot ishlayapti" if bot_active else "🔴 Bot to'xtatilgan")
    )
    kb = admin_main_kb(bot_active)
    if isinstance(target, CallbackQuery):
        await target.message.edit_text(full_text, reply_markup=kb, parse_mode="HTML")
    else:
        await target.answer(full_text, reply_markup=kb, parse_mode="HTML")


# ══════════════════════════════════════════════════════════════════════════════
# /admin KOMANDA
# ══════════════════════════════════════════════════════════════════════════════

@admin_router.message(Command("admin"))
async def cmd_admin(message: Message, session: AsyncSession):
    if not await _admin_check(message, session):
        return
    await _send_admin_panel(message, session)


# ══════════════════════════════════════════════════════════════════════════════
# ASOSIY PANEL NAVIGATSIYA
# ══════════════════════════════════════════════════════════════════════════════

@admin_router.callback_query(F.data == "admin:back_main")
async def back_to_main(call: CallbackQuery, session: AsyncSession, state: FSMContext):
    if not await _admin_check(call, session):
        return
    await call.answer()
    await state.clear()
    await _send_admin_panel(call, session)


# ══════════════════════════════════════════════════════════════════════════════
# BOT HOLATI — TO'XTATISH / YOQISH
# ══════════════════════════════════════════════════════════════════════════════

@admin_router.callback_query(F.data == "admin:stop_bot")
async def stop_bot(call: CallbackQuery, session: AsyncSession):
    if not await _admin_check(call, session):
        return
    await crud.set_bot_active(session, False)
    await call.answer("🔴 Bot to'xtatildi.", show_alert=True)
    await _send_admin_panel(call, session)


@admin_router.callback_query(F.data == "admin:start_bot")
async def start_bot(call: CallbackQuery, session: AsyncSession):
    if not await _admin_check(call, session):
        return
    await crud.set_bot_active(session, True)
    await call.answer("🟢 Bot ishga tushirildi.", show_alert=True)
    await _send_admin_panel(call, session)


# ══════════════════════════════════════════════════════════════════════════════
# KINOLAR BOSHQARUVI
# ══════════════════════════════════════════════════════════════════════════════

@admin_router.callback_query(F.data == "admin:movies")
async def movies_panel(call: CallbackQuery, session: AsyncSession):
    if not await _admin_check(call, session):
        return
    await call.answer()
    await call.message.edit_text("🎬 Kinolar boshqaruvi:", reply_markup=admin_movies_kb())


# ──── Kino ro'yxati ──────────────────────────────────────────────────────── #

@admin_router.callback_query(F.data == "admin:list_movies")
async def list_movies(call: CallbackQuery, session: AsyncSession):
    if not await _admin_check(call, session):
        return
    await call.answer()
    for cat in CATEGORIES:
        movies, total = await crud.get_movies_by_category(session, cat)
        if movies:
            lines = [f"📂 <b>{cat}</b> ({total} ta):"]
            for m in movies:
                lines.append(f"  🎬 <code>{m.code}</code> — {m.title}")
            await call.message.answer("\n".join(lines), parse_mode="HTML")
    await call.message.answer(
        "Ro'yxat yuborildi.",
        reply_markup=back_kb("admin:movies"),
    )


# ──── Kino qo'shish ──────────────────────────────────────────────────────── #

@admin_router.callback_query(F.data == "admin:add_movie")
async def add_movie_start(call: CallbackQuery, session: AsyncSession, state: FSMContext):
    if not await _admin_check(call, session):
        return
    await call.answer()
    await call.message.edit_text(
        "➕ <b>Kino qo'shish</b>\n\n"
        "Arxiv kanalidan kino xabarini botga <b>forward</b> qiling,\n"
        "yoki <b>kanal ID va xabar ID</b> ni quyidagi ko'rinishda yuboring:\n"
        "<code>-1001234567890:123</code>",
        parse_mode="HTML",
        reply_markup=cancel_kb("admin:movies"),
    )
    await state.set_state(AddMovieFSM.waiting_forward)


@admin_router.message(AddMovieFSM.waiting_forward)
async def add_movie_forward(message: Message, session: AsyncSession, state: FSMContext, bot: Bot):
    if not await _admin_check(message, session):
        return

    channel_id = None
    msg_id = None

    # Forward orqali
    if message.forward_from_chat:
        channel_id = message.forward_from_chat.id
        msg_id = message.forward_from_message_id
    else:
        # Qo'lda kiritilgan format: channel_id:message_id
        text = message.text.strip() if message.text else ""
        if ":" in text:
            parts = text.split(":")
            try:
                channel_id = int(parts[0])
                msg_id = int(parts[1])
            except (ValueError, IndexError):
                await message.answer(
                    "❌ Noto'g'ri format. <code>-1001234567890:123</code> ko'rinishida yuboring.",
                    parse_mode="HTML",
                )
                return
        else:
            await message.answer(
                "❌ Forward qiling yoki <code>kanal_id:xabar_id</code> formatida yuboring.",
                parse_mode="HTML",
            )
            return

    # Kanal huquqlarini tekshirish
    ok, err_msg = await check_bot_channel_rights(bot, channel_id)
    if not ok:
        await message.answer(
            f"{err_msg}\n\n"
            "Kanal ID va xabar ID to'g'riligini tekshiring.",
            reply_markup=cancel_kb("admin:movies"),
        )
        return

    await state.update_data(channel_id=channel_id, message_id=msg_id)
    await message.answer(
        f"✅ Kanal tasdiqlandi: <code>{channel_id}</code>\n"
        f"Xabar ID: <code>{msg_id}</code>\n\n"
        "🔑 Kino uchun noyob <b>kod</b> kiriting (masalan: <code>001</code>):",
        parse_mode="HTML",
        reply_markup=cancel_kb("admin:movies"),
    )
    await state.set_state(AddMovieFSM.waiting_code)


@admin_router.message(AddMovieFSM.waiting_code)
async def add_movie_code(message: Message, session: AsyncSession, state: FSMContext):
    if not await _admin_check(message, session):
        return
    code = message.text.strip()
    if not code or len(code) > 50:
        await message.answer("❌ Kod 1-50 ta belgi bo'lishi kerak.")
        return

    # Mavjudligini tekshirish
    existing = await crud.get_movie_by_code(session, code)
    if existing:
        await message.answer(
            f"❌ <code>{code}</code> kodi allaqachon mavjud: <b>{existing.title}</b>\n"
            "Boshqa kod kiriting:",
            parse_mode="HTML",
        )
        return

    await state.update_data(code=code)
    await message.answer(
        f"✅ Kod: <code>{code}</code>\n\n"
        "📝 Kino <b>nomini</b> kiriting:",
        parse_mode="HTML",
        reply_markup=cancel_kb("admin:movies"),
    )
    await state.set_state(AddMovieFSM.waiting_title)


@admin_router.message(AddMovieFSM.waiting_title)
async def add_movie_title(message: Message, session: AsyncSession, state: FSMContext):
    if not await _admin_check(message, session):
        return
    title = message.text.strip()
    if not title or len(title) > 500:
        await message.answer("❌ Nom 1-500 ta belgi bo'lishi kerak.")
        return
    await state.update_data(title=title)

    # Kategoriya tanlash
    from aiogram.types import InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    for cat in CATEGORIES:
        builder.button(text=cat, callback_data=f"add_cat:{cat}")
    builder.adjust(1)
    builder.row(InlineKeyboardButton(text="🚫 Bekor qilish", callback_data="admin:movies"))

    await message.answer(
        f"✅ Nom: <b>{title}</b>\n\n"
        "📂 <b>Kategoriyani</b> tanlang:",
        parse_mode="HTML",
        reply_markup=builder.as_markup(),
    )
    await state.set_state(AddMovieFSM.waiting_category)


@admin_router.callback_query(AddMovieFSM.waiting_category, F.data.startswith("add_cat:"))
async def add_movie_category(call: CallbackQuery, session: AsyncSession, state: FSMContext):
    if not await _admin_check(call, session):
        return
    await call.answer()
    category = call.data.split(":", 1)[1]
    data = await state.get_data()
    await state.update_data(category=category)

    text = (
        f"📋 <b>Kino ma'lumotlari:</b>\n\n"
        f"🔑 Kod: <code>{data['code']}</code>\n"
        f"📝 Nom: <b>{data['title']}</b>\n"
        f"📂 Kategoriya: {category}\n"
        f"📺 Kanal ID: <code>{data['channel_id']}</code>\n"
        f"🔢 Xabar ID: <code>{data['message_id']}</code>\n\n"
        "Tasdiqlaysizmi?"
    )
    await call.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=confirm_kb("add_movie_confirm", "admin:movies"),
    )
    await state.set_state(AddMovieFSM.confirm)


@admin_router.callback_query(AddMovieFSM.confirm, F.data == "add_movie_confirm")
async def add_movie_confirm(call: CallbackQuery, session: AsyncSession, state: FSMContext):
    if not await _admin_check(call, session):
        return
    await call.answer()
    data = await state.get_data()
    await state.clear()

    movie, err = await crud.add_movie(
        session=session,
        code=data["code"],
        title=data["title"],
        category=data["category"],
        channel_id=data["channel_id"],
        message_id=data["message_id"],
        added_by=call.from_user.id,
    )
    if err:
        await call.message.edit_text(err, reply_markup=back_kb("admin:movies"))
    else:
        await call.message.edit_text(
            f"✅ <b>{movie.title}</b> kinosi qo'shildi!\n"
            f"🔑 Kod: <code>{movie.code}</code>",
            parse_mode="HTML",
            reply_markup=back_kb("admin:movies"),
        )


# ──── Kino tahrirlash ────────────────────────────────────────────────────── #

@admin_router.callback_query(F.data == "admin:edit_movie")
async def edit_movie_start(call: CallbackQuery, session: AsyncSession, state: FSMContext):
    if not await _admin_check(call, session):
        return
    await call.answer()
    await call.message.edit_text(
        "✏️ <b>Kino tahrirlash</b>\n\nKino kodini kiriting:",
        parse_mode="HTML",
        reply_markup=cancel_kb("admin:movies"),
    )
    await state.set_state(EditMovieFSM.waiting_code)


@admin_router.message(EditMovieFSM.waiting_code)
async def edit_movie_code(message: Message, session: AsyncSession, state: FSMContext):
    if not await _admin_check(message, session):
        return
    code = message.text.strip()
    movie = await crud.get_movie_by_code(session, code)
    if not movie:
        await message.answer(f"❌ <code>{code}</code> kodi topilmadi.", parse_mode="HTML")
        return
    await state.update_data(movie_id=movie.id, old_code=code)

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.button(text="🔑 Kod", callback_data="edit_field:code")
    builder.button(text="📝 Nom", callback_data="edit_field:title")
    builder.button(text="📂 Kategoriya", callback_data="edit_field:category")
    builder.button(text="🚫 Bekor qilish", callback_data="admin:movies")
    builder.adjust(3, 1)

    await message.answer(
        f"✏️ <b>{movie.title}</b>\nQaysi maydonni tahrirlash?",
        parse_mode="HTML",
        reply_markup=builder.as_markup(),
    )
    await state.set_state(EditMovieFSM.choose_field)


@admin_router.callback_query(EditMovieFSM.choose_field, F.data.startswith("edit_field:"))
async def edit_movie_field(call: CallbackQuery, state: FSMContext):
    await call.answer()
    field = call.data.split(":")[1]
    prompts = {
        "code": "Yangi kodni kiriting:",
        "title": "Yangi nomni kiriting:",
        "category": "Yangi kategoriyani kiriting:\n" + "\n".join(f"• {c}" for c in CATEGORIES),
    }
    await state.update_data(field=field)
    await call.message.edit_text(
        prompts.get(field, "Yangi qiymatni kiriting:"),
        reply_markup=cancel_kb("admin:movies"),
    )
    await state.set_state(EditMovieFSM.waiting_value)


@admin_router.message(EditMovieFSM.waiting_value)
async def edit_movie_value(message: Message, session: AsyncSession, state: FSMContext):
    if not await _admin_check(message, session):
        return
    data = await state.get_data()
    field = data["field"]
    value = message.text.strip()

    if field == "category" and value not in CATEGORIES:
        await message.answer(
            f"❌ Noto'g'ri kategoriya. Quyidagilardan birini tanlang:\n"
            + "\n".join(f"• {c}" for c in CATEGORIES)
        )
        return
    if field == "code":
        existing = await crud.get_movie_by_code(session, value)
        if existing and existing.id != data["movie_id"]:
            await message.answer(f"❌ <code>{value}</code> kodi allaqachon mavjud.", parse_mode="HTML")
            return

    ok = await crud.update_movie(session, data["movie_id"], **{field: value})
    await state.clear()
    if ok:
        await message.answer(
            f"✅ Muvaffaqiyatli yangilandi: <b>{field}</b> → <code>{value}</code>",
            parse_mode="HTML",
            reply_markup=back_kb("admin:movies"),
        )
    else:
        await message.answer("❌ Yangilashda xatolik.", reply_markup=back_kb("admin:movies"))


# ──── Kino o'chirish ─────────────────────────────────────────────────────── #

@admin_router.callback_query(F.data == "admin:delete_movie")
async def delete_movie_start(call: CallbackQuery, session: AsyncSession, state: FSMContext):
    if not await _admin_check(call, session):
        return
    await call.answer()
    await call.message.edit_text(
        "🗑 <b>Kino o'chirish</b>\n\nKino kodini kiriting:",
        parse_mode="HTML",
        reply_markup=cancel_kb("admin:movies"),
    )
    await state.set_state(DeleteMovieFSM.waiting_code)


@admin_router.message(DeleteMovieFSM.waiting_code)
async def delete_movie_code(message: Message, session: AsyncSession, state: FSMContext):
    if not await _admin_check(message, session):
        return
    code = message.text.strip()
    movie = await crud.get_movie_by_code(session, code)
    if not movie:
        await message.answer(f"❌ <code>{code}</code> kodi topilmadi.", parse_mode="HTML")
        return
    await state.update_data(code=code)
    await message.answer(
        f"🗑 <b>{movie.title}</b> (<code>{code}</code>) kinoni o'chirasizmi?\n"
        "Bu amalni bekor qilib bo'lmaydi!",
        parse_mode="HTML",
        reply_markup=confirm_kb(f"del_movie_confirm:{code}", "admin:movies"),
    )
    await state.set_state(DeleteMovieFSM.confirm)


@admin_router.callback_query(DeleteMovieFSM.confirm, F.data.startswith("del_movie_confirm:"))
async def delete_movie_confirm(call: CallbackQuery, session: AsyncSession, state: FSMContext):
    if not await _admin_check(call, session):
        return
    await call.answer()
    code = call.data.split(":", 1)[1]
    await state.clear()
    ok = await crud.delete_movie(session, code)
    if ok:
        await call.message.edit_text(
            f"✅ <code>{code}</code> kodi o'chirildi.",
            parse_mode="HTML",
            reply_markup=back_kb("admin:movies"),
        )
    else:
        await call.message.edit_text("❌ O'chirishda xatolik.", reply_markup=back_kb("admin:movies"))


# ══════════════════════════════════════════════════════════════════════════════
# MAJBURIY KANALLAR
# ══════════════════════════════════════════════════════════════════════════════

@admin_router.callback_query(F.data == "admin:channels")
async def channels_panel(call: CallbackQuery, session: AsyncSession):
    if not await _admin_check(call, session):
        return
    await call.answer()
    channels = await crud.get_required_channels(session)
    text = ("📢 <b>Majburiy kanallar</b>\n"
            "Arxiv kanali obuna ro‘yxatiga avtomatik qo‘shilmaydi.\n"
            "Tekshirish uchun oddiy foydalanuvchi akkauntidan kiring; "
            "admin obunadan ozod.\n")
    if not channels:
        text += "\nHozircha kanallar yo'q."
    await call.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=admin_channels_kb(channels),
    )


@admin_router.callback_query(F.data == "admin:add_channel")
async def add_channel_start(call: CallbackQuery, session: AsyncSession, state: FSMContext):
    if not await _admin_check(call, session):
        return
    await call.answer()
    await call.message.edit_text(
        "➕ <b>Kanal qo'shish</b>\n\n"
        "Kanal ID raqamini yuboring (masalan: <code>-1001234567890</code>)\n\n"
        "<i>Kanal ID ni bilish uchun kanalga @username_to_id_bot ni qo'shing.</i>",
        parse_mode="HTML",
        reply_markup=cancel_kb("admin:channels"),
    )
    await state.set_state(AddChannelFSM.waiting_channel_id)


@admin_router.message(AddChannelFSM.waiting_channel_id)
async def add_channel_id(message: Message, session: AsyncSession, state: FSMContext, bot: Bot):
    if not await _admin_check(message, session):
        return
    text = message.text.strip()
    try:
        channel_id = int(text)
    except ValueError:
        await message.answer("❌ Noto'g'ri format. Raqam kiriting (masalan: <code>-1001234567890</code>).", parse_mode="HTML")
        return

    # Huquqlarni tekshirish
    ok, err = await check_bot_channel_rights(bot, channel_id)
    if not ok:
        await message.answer(
            f"{err}\n\nBot kanalda admin bo'lishi va a'zolarni tekshirish huquqiga ega bo'lishi kerak.",
            reply_markup=cancel_kb("admin:channels"),
        )
        return

    # Kanal nomini olish
    try:
        chat = await bot.get_chat(channel_id)
        title = chat.title or str(channel_id)
    except Exception:
        title = str(channel_id)

    await state.update_data(channel_id=channel_id, channel_title=title)
    await message.answer(
        f"✅ Kanal: <b>{title}</b>\n\n"
        "🔗 Kanalga kirish havolasini yuboring (masalan: <code>https://t.me/kanal_nomi</code>):",
        parse_mode="HTML",
        reply_markup=cancel_kb("admin:channels"),
    )
    await state.set_state(AddChannelFSM.waiting_invite_link)


@admin_router.message(AddChannelFSM.waiting_invite_link)
async def add_channel_link(message: Message, session: AsyncSession, state: FSMContext):
    if not await _admin_check(message, session):
        return
    link = message.text.strip()
    if not link.startswith("https://t.me/") and not link.startswith("http://t.me/"):
        await message.answer(
            "❌ Havola <code>https://t.me/</code> bilan boshlanishi kerak.",
            parse_mode="HTML",
        )
        return
    data = await state.get_data()
    await state.update_data(invite_link=link)
    await message.answer(
        f"📢 <b>{data['channel_title']}</b>\n"
        f"🔗 {link}\n\nQo'shilsinmi?",
        reply_markup=confirm_kb("add_ch_confirm", "admin:channels"),
    )
    await state.set_state(AddChannelFSM.confirm)


@admin_router.callback_query(AddChannelFSM.confirm, F.data == "add_ch_confirm")
async def add_channel_confirm(call: CallbackQuery, session: AsyncSession, state: FSMContext):
    if not await _admin_check(call, session):
        return
    await call.answer()
    data = await state.get_data()
    await state.clear()
    ch, err = await crud.add_required_channel(
        session=session,
        channel_id=data["channel_id"],
        channel_title=data["channel_title"],
        invite_link=data["invite_link"],
    )
    await session.commit()
    if err:
        await call.message.edit_text(err, reply_markup=back_kb("admin:channels"))
    else:
        await call.message.edit_text(
            f"✅ <b>{ch.channel_title}</b> kanali qo'shildi!",
            parse_mode="HTML",
            reply_markup=back_kb("admin:channels"),
        )


@admin_router.callback_query(F.data.startswith("admin:rm_channel:"))
async def remove_channel(call: CallbackQuery, session: AsyncSession):
    if not await _admin_check(call, session):
        return
    channel_id = int(call.data.split(":")[2])
    ok = await crud.remove_required_channel(session, channel_id)
    channels = await crud.get_required_channels(session)
    text = "📢 <b>Majburiy kanallar</b>\n" + ("" if channels else "\nHozircha kanallar yo'q.")
    await call.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=admin_channels_kb(channels),
    )
    await call.answer("✅ Kanal olib tashlandi." if ok else "❌ Xatolik.")


# ══════════════════════════════════════════════════════════════════════════════
# ARXIV KANALI SOZLAMASI
# ══════════════════════════════════════════════════════════════════════════════

@admin_router.callback_query(F.data == "admin:set_archive")
async def set_archive_start(call: CallbackQuery, session: AsyncSession, state: FSMContext):
    if not await _admin_check(call, session):
        return
    await call.answer()
    await call.message.edit_text(
        "📦 <b>Arxiv kanali</b>\n\n"
        "Yangi arxiv kanal ID raqamini yuboring.\n"
        "⚠️ Bu faqat keyingi qo'shiladigan kinolarga ta'sir qiladi.\n"
        "Eski kinolar o'z kanalida qoladi.",
        parse_mode="HTML",
        reply_markup=cancel_kb("admin:settings"),
    )
    await state.set_state(SetArchiveFSM.waiting_channel_id)


@admin_router.message(SetArchiveFSM.waiting_channel_id)
async def set_archive_channel(message: Message, session: AsyncSession, state: FSMContext, bot: Bot):
    if not await _admin_check(message, session):
        return
    text = message.text.strip()
    try:
        channel_id = int(text)
    except ValueError:
        await message.answer("❌ Noto'g'ri format. Raqam kiriting.")
        return

    ok, err = await check_bot_channel_rights(bot, channel_id)
    if not ok:
        await message.answer(err, reply_markup=cancel_kb("admin:settings"))
        return

    try:
        chat = await bot.get_chat(channel_id)
        title = chat.title or str(channel_id)
    except Exception:
        title = str(channel_id)

    await crud.set_setting(session, "default_archive_channel", str(channel_id))
    await state.clear()
    await message.answer(
        f"✅ Yangi arxiv kanali: <b>{title}</b> (<code>{channel_id}</code>)",
        parse_mode="HTML",
        reply_markup=back_kb("admin:settings"),
    )


# ══════════════════════════════════════════════════════════════════════════════
# SOZLAMALAR
# ══════════════════════════════════════════════════════════════════════════════

@admin_router.callback_query(F.data == "admin:settings")
async def settings_panel(call: CallbackQuery, session: AsyncSession):
    if not await _admin_check(call, session):
        return
    await call.answer()
    contact = await crud.get_admin_contact(session)
    archive = await crud.get_setting(session, "default_archive_channel", "Sozlanmagan")
    await call.message.edit_text(
        f"⚙️ <b>Sozlamalar</b>\n\n"
        f"📱 Admin kontakt: @{contact or 'sozlanmagan'}\n"
        f"📦 Standart arxiv kanal: <code>{archive}</code>",
        parse_mode="HTML",
        reply_markup=admin_settings_kb(),
    )


@admin_router.callback_query(F.data == "admin:set_contact")
async def set_contact_start(call: CallbackQuery, session: AsyncSession, state: FSMContext):
    if not await _admin_check(call, session):
        return
    await call.answer()
    await call.message.edit_text(
        "📱 Admin username kiriting (@ belgisisiz):",
        reply_markup=cancel_kb("admin:settings"),
    )
    await state.set_state(SetContactFSM.waiting_username)


@admin_router.message(SetContactFSM.waiting_username)
async def set_contact_username(message: Message, session: AsyncSession, state: FSMContext):
    if not await _admin_check(message, session):
        return
    username = message.text.strip().lstrip("@")
    if not username:
        await message.answer("❌ Username bo'sh bo'lishi mumkin emas.")
        return
    await crud.set_admin_contact(session, username)
    await state.clear()
    await message.answer(
        f"✅ Admin kontakt yangilandi: @{username}",
        reply_markup=back_kb("admin:settings"),
    )


# ══════════════════════════════════════════════════════════════════════════════
# BROADCAST — BITTA FOYDALANUVCHI
# ══════════════════════════════════════════════════════════════════════════════

@admin_router.callback_query(F.data == "admin:broadcast")
async def broadcast_panel(call: CallbackQuery, session: AsyncSession):
    if not await _admin_check(call, session):
        return
    await call.answer()
    await call.message.edit_text(
        "📨 <b>Xabar yuborish</b>",
        parse_mode="HTML",
        reply_markup=admin_broadcast_kb(),
    )


@admin_router.callback_query(F.data == "admin:bc_one")
async def bc_one_start(call: CallbackQuery, session: AsyncSession, state: FSMContext):
    if not await _admin_check(call, session):
        return
    await call.answer()
    await call.message.edit_text(
        "👤 <b>Bitta foydalanuvchiga xabar</b>\n\nQaysi usul?",
        parse_mode="HTML",
        reply_markup=bc_user_select_kb(),
    )
    await state.set_state(BroadcastOneFSM.choose_method)


@admin_router.callback_query(BroadcastOneFSM.choose_method, F.data.in_({"admin:bc_by_username", "admin:bc_by_id"}))
async def bc_one_choose_method(call: CallbackQuery, state: FSMContext):
    await call.answer()
    method = "username" if call.data == "admin:bc_by_username" else "id"
    await state.update_data(method=method)
    prompt = "Username kiriting (@ bilan yoki siz):" if method == "username" else "Telegram ID raqamini kiriting:"
    await call.message.edit_text(prompt, reply_markup=cancel_kb("admin:broadcast"))
    await state.set_state(BroadcastOneFSM.waiting_identifier)


@admin_router.message(BroadcastOneFSM.waiting_identifier)
async def bc_one_identifier(message: Message, session: AsyncSession, state: FSMContext):
    if not await _admin_check(message, session):
        return
    data = await state.get_data()
    method = data.get("method", "username")
    text = message.text.strip()

    user = None
    if method == "username":
        user = await crud.get_user_by_username(session, text)
        if not user:
            await message.answer(
                "❌ Bu username bilan foydalanuvchi topilmadi.\n"
                "<i>Foydalanuvchi bot bilan muloqot qilmagan bo'lishi mumkin.</i>",
                parse_mode="HTML",
            )
            return
    else:
        try:
            tg_id = int(text)
        except ValueError:
            await message.answer("❌ Noto'g'ri ID. Raqam kiriting.")
            return
        user = await crud.get_user_by_telegram_id(session, tg_id)
        if not user:
            await message.answer(
                "❌ Bu ID bilan foydalanuvchi topilmadi.\n"
                "<i>Foydalanuvchi bot bilan muloqot qilmagan bo'lishi mumkin.</i>",
                parse_mode="HTML",
            )
            return

    await state.update_data(target_tg_id=user.telegram_id)
    await message.answer(
        f"👤 Topildi:\n"
        f"📛 Ismi: <b>{user.full_name}</b>\n"
        f"🔗 Username: @{user.username or '—'}\n"
        f"🆔 ID: <code>{user.telegram_id}</code>\n\n"
        "Ushbu foydalanuvchiga yuboriladigan xabarni yozing (matn, rasm, video, hujjat):",
        parse_mode="HTML",
        reply_markup=cancel_kb("admin:broadcast"),
    )
    await state.set_state(BroadcastOneFSM.waiting_message)


@admin_router.message(BroadcastOneFSM.waiting_message)
async def bc_one_message(message: Message, state: FSMContext):
    media_type, file_id, caption, text = _extract_message_content(message)
    await state.update_data(
        media_type=media_type, file_id=file_id,
        caption=caption, text=text,
    )
    data = await state.get_data()

    preview = caption or text or "📎 Media fayl"
    await message.answer(
        f"📨 Xabar namunasi:\n{preview[:300]}\n\n"
        f"📬 Qabul qiluvchi ID: <code>{data['target_tg_id']}</code>\n\nYuborilsinmi?",
        parse_mode="HTML",
        reply_markup=confirm_kb("bc_one_confirm", "admin:broadcast"),
    )
    await state.set_state(BroadcastOneFSM.confirm_send)


@admin_router.callback_query(BroadcastOneFSM.confirm_send, F.data == "bc_one_confirm")
async def bc_one_confirm(call: CallbackQuery, session: AsyncSession, state: FSMContext, bot: Bot):
    if not await _admin_check(call, session):
        return
    await call.answer()
    data = await state.get_data()
    await state.clear()

    from utils.helpers import safe_send_message
    ok, err = await safe_send_message(
        bot=bot,
        chat_id=data["target_tg_id"],
        text=data.get("text"),
        media_type=data.get("media_type"),
        media_file_id=data.get("file_id"),
        caption=data.get("caption"),
    )
    if ok:
        await call.message.edit_text("✅ Xabar yuborildi!", reply_markup=back_kb("admin:broadcast"))
    else:
        if err == "blocked":
            await call.message.edit_text(
                "❌ Foydalanuvchi botni bloklagan.",
                reply_markup=back_kb("admin:broadcast"),
            )
        else:
            await call.message.edit_text(
                f"❌ Yuborishda xato: {err}",
                reply_markup=back_kb("admin:broadcast"),
            )


# ══════════════════════════════════════════════════════════════════════════════
# BROADCAST — BARCHAGA
# ══════════════════════════════════════════════════════════════════════════════

@admin_router.callback_query(F.data == "admin:bc_all")
async def bc_all_start(call: CallbackQuery, session: AsyncSession, state: FSMContext):
    if not await _admin_check(call, session):
        return
    await call.answer()
    count = await crud.count_users(session)
    await call.message.edit_text(
        f"👥 <b>Barcha foydalanuvchilarga xabar</b>\n\n"
        f"Jami: <b>{count}</b> foydalanuvchi\n\n"
        "Yuboriladigan xabarni yozing (matn, rasm, video, hujjat):",
        parse_mode="HTML",
        reply_markup=cancel_kb("admin:broadcast"),
    )
    await state.set_state(BroadcastAllFSM.waiting_message)


@admin_router.message(BroadcastAllFSM.waiting_message)
async def bc_all_message(message: Message, session: AsyncSession, state: FSMContext):
    media_type, file_id, caption, text = _extract_message_content(message)
    await state.update_data(
        media_type=media_type, file_id=file_id,
        caption=caption, text=text,
    )
    count = await crud.count_users(session)
    preview = caption or text or "📎 Media fayl"
    await message.answer(
        f"📨 <b>Xabar namunasi:</b>\n{preview[:300]}\n\n"
        f"👥 Qabul qiluvchilar: <b>{count}</b> foydalanuvchi\n\nYuborilsinmi?",
        parse_mode="HTML",
        reply_markup=confirm_kb("bc_all_confirm", "admin:broadcast"),
    )
    await state.set_state(BroadcastAllFSM.confirm)


@admin_router.callback_query(BroadcastAllFSM.confirm, F.data == "bc_all_confirm")
async def bc_all_confirm(call: CallbackQuery, session: AsyncSession, state: FSMContext, bot: Bot):
    if not await _admin_check(call, session):
        return
    await call.answer()
    data = await state.get_data()
    await state.clear()

    import uuid
    broadcast_id = str(uuid.uuid4())
    users = await crud.get_all_active_users(session)

    await call.message.edit_text(
        f"📤 Yuborish boshlandi... ({len(users)} foydalanuvchi)"
    )

    # Broadcast fonga o'tkaziladi
    import asyncio
    from config import BROADCAST_DELAY
    asyncio.create_task(
        _run_broadcast(
            bot=bot,
            users=users,
            broadcast_id=broadcast_id,
            admin_id=call.from_user.id,
            text=data.get("text"),
            media_type=data.get("media_type"),
            file_id=data.get("file_id"),
            caption=data.get("caption"),
            notify_chat_id=call.message.chat.id,
        )
    )


async def _run_broadcast(
    bot: Bot,
    users,
    broadcast_id: str,
    admin_id: int,
    text: str | None,
    media_type: str | None,
    file_id: str | None,
    caption: str | None,
    notify_chat_id: int,
):
    """Fonga ishlaydigan broadcast."""
    import asyncio
    from config import BROADCAST_DELAY
    from utils.helpers import safe_send_message
    from database.engine import AsyncSessionLocal

    success = 0
    failed = 0
    blocked = 0

    for user in users:
        ok, err = await safe_send_message(
            bot=bot,
            chat_id=user.telegram_id,
            text=text,
            media_type=media_type,
            media_file_id=file_id,
            caption=caption,
        )
        if ok:
            success += 1
        elif err == "blocked":
            blocked += 1
            # Bloklangan foydalanuvchini belgilash
            async with AsyncSessionLocal() as session:
                from database.crud import mark_user_blocked
                await mark_user_blocked(session, user.telegram_id)
                await session.commit()
        else:
            failed += 1
            logger.warning("Broadcast xato user=%s: %s", user.telegram_id, err)

        # RetryAfter boshqaruvi
        if "retry_after:" in str(err):
            try:
                wait = int(str(err).split(":")[1])
                await asyncio.sleep(wait)
            except Exception:
                await asyncio.sleep(30)

        await asyncio.sleep(BROADCAST_DELAY)

    # Admin natija xabari
    try:
        await bot.send_message(
            chat_id=notify_chat_id,
            text=(
                f"📊 <b>Broadcast yakunlandi</b>\n\n"
                f"✅ Muvaffaqiyatli: {success}\n"
                f"🚫 Bloklagan: {blocked}\n"
                f"❌ Xato: {failed}\n"
                f"📬 Jami: {success + failed + blocked}"
            ),
            parse_mode="HTML",
        )
    except Exception as e:
        logger.error("Broadcast natija xabarini yuborishda xato: %s", e)


# ══════════════════════════════════════════════════════════════════════════════
# REJALASHTIRILGAN XABARLAR
# ══════════════════════════════════════════════════════════════════════════════

@admin_router.callback_query(F.data == "admin:schedules")
async def schedules_panel(call: CallbackQuery, session: AsyncSession):
    if not await _admin_check(call, session):
        return
    await call.answer()
    schedules = await crud.get_all_schedules(session)
    await call.message.edit_text(
        f"📅 <b>Rejalashtirilgan xabarlar</b> ({len(schedules)} ta):",
        parse_mode="HTML",
        reply_markup=admin_schedule_kb(schedules),
    )


@admin_router.callback_query(F.data.startswith("admin:sch_view:"))
async def schedule_view(call: CallbackQuery, session: AsyncSession):
    if not await _admin_check(call, session):
        return
    sch_id = int(call.data.split(":")[2])
    sch = await crud.get_schedule_by_id(session, sch_id)
    if not sch:
        await call.answer("❌ Topilmadi.", show_alert=True)
        return

    recipient = "👥 Barcha" if sch.recipient_type == "all" else f"👤 ID: {sch.recipient_id}"
    status_map = {"active": "▶️ Faol", "paused": "⏸ Pauza", "finished": "✅ Tugadi", "cancelled": "❌ Bekor"}
    preview = sch.caption or sch.text or "📎 Media"

    await call.message.edit_text(
        f"📅 <b>Jadval #{sch.id}</b>\n\n"
        f"📝 Xabar: {preview[:200]}\n"
        f"📬 Qabul qiluvchi: {recipient}\n"
        f"📅 Boshlanish: {sch.start_date}\n"
        f"⏰ Vaqt: {sch.send_time} (Toshkent)\n"
        f"📆 Davomiylik: {sch.duration_days} kun\n"
        f"📊 Holat: {status_map.get(sch.status, sch.status)}",
        parse_mode="HTML",
        reply_markup=schedule_actions_kb(sch),
    )
    await call.answer()


@admin_router.callback_query(F.data.startswith("admin:sch_pause:"))
async def schedule_pause(call: CallbackQuery, session: AsyncSession):
    if not await _admin_check(call, session):
        return
    sch_id = int(call.data.split(":")[2])
    await crud.update_schedule_status(session, sch_id, "paused")
    await call.answer("⏸ Pauza qilindi.")
    sch = await crud.get_schedule_by_id(session, sch_id)
    await call.message.edit_reply_markup(reply_markup=schedule_actions_kb(sch))


@admin_router.callback_query(F.data.startswith("admin:sch_resume:"))
async def schedule_resume(call: CallbackQuery, session: AsyncSession):
    if not await _admin_check(call, session):
        return
    sch_id = int(call.data.split(":")[2])
    await crud.update_schedule_status(session, sch_id, "active")
    await call.answer("▶️ Davom ettirildi.")
    sch = await crud.get_schedule_by_id(session, sch_id)
    await call.message.edit_reply_markup(reply_markup=schedule_actions_kb(sch))


@admin_router.callback_query(F.data.startswith("admin:sch_cancel:"))
async def schedule_cancel(call: CallbackQuery, session: AsyncSession):
    if not await _admin_check(call, session):
        return
    sch_id = int(call.data.split(":")[2])
    await crud.update_schedule_status(session, sch_id, "cancelled")
    await call.answer("❌ Bekor qilindi.")
    schedules = await crud.get_all_schedules(session)
    await call.message.edit_text(
        f"📅 <b>Rejalashtirilgan xabarlar</b> ({len(schedules)} ta):",
        parse_mode="HTML",
        reply_markup=admin_schedule_kb(schedules),
    )


# ──── Yangi jadval yaratish ──────────────────────────────────────────────── #

@admin_router.callback_query(F.data == "admin:sch_new")
async def schedule_new_start(call: CallbackQuery, session: AsyncSession, state: FSMContext):
    if not await _admin_check(call, session):
        return
    await call.answer()
    await call.message.edit_text(
        "📅 <b>Yangi jadval</b>\n\n"
        "<b>1-qadam:</b> Yuboriladigan xabarni yozing (matn, rasm, video yoki hujjat):",
        parse_mode="HTML",
        reply_markup=cancel_kb("admin:schedules"),
    )
    await state.set_state(ScheduleFSM.waiting_content)


@admin_router.message(ScheduleFSM.waiting_content)
async def schedule_content(message: Message, state: FSMContext):
    media_type, file_id, caption, text = _extract_message_content(message)
    await state.update_data(media_type=media_type, file_id=file_id, caption=caption, text=text)

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.button(text="👥 Barcha foydalanuvchilar", callback_data="sch_rec:all")
    builder.button(text="👤 Bitta foydalanuvchi", callback_data="sch_rec:one")
    builder.button(text="🚫 Bekor qilish", callback_data="admin:schedules")
    builder.adjust(2, 1)

    await message.answer(
        "✅ Xabar qabul qilindi.\n\n"
        "<b>2-qadam:</b> Kimga yuborilsin?",
        parse_mode="HTML",
        reply_markup=builder.as_markup(),
    )
    await state.set_state(ScheduleFSM.waiting_recipient)


@admin_router.callback_query(ScheduleFSM.waiting_recipient, F.data.startswith("sch_rec:"))
async def schedule_recipient(call: CallbackQuery, state: FSMContext, session: AsyncSession):
    await call.answer()
    rec_type = call.data.split(":")[1]
    await state.update_data(recipient_type=rec_type)

    if rec_type == "one":
        await call.message.edit_text(
            "👤 Foydalanuvchi Telegram ID raqamini kiriting:",
            reply_markup=cancel_kb("admin:schedules"),
        )
        # Keyingi bosqich recipient_id so'raydi (matn orqali)
        await state.set_state(ScheduleFSM.waiting_start_date)
        await state.update_data(waiting_recipient_id=True)
    else:
        await state.update_data(recipient_id=None, waiting_recipient_id=False)
        await call.message.edit_text(
            "📅 <b>3-qadam:</b> Boshlanish sanasini kiriting (YYYY-MM-DD):\n"
            "<i>Masalan: 2026-10-10</i>",
            parse_mode="HTML",
            reply_markup=cancel_kb("admin:schedules"),
        )
        await state.set_state(ScheduleFSM.waiting_start_date)


@admin_router.message(ScheduleFSM.waiting_start_date)
async def schedule_start_date(message: Message, state: FSMContext):
    import re
    from datetime import date
    data = await state.get_data()
    text = message.text.strip()

    # Recipient ID kutilayotgan bo'lsa
    if data.get("waiting_recipient_id"):
        try:
            rid = int(text)
            await state.update_data(recipient_id=rid, waiting_recipient_id=False)
            await message.answer(
                "📅 <b>3-qadam:</b> Boshlanish sanasini kiriting (YYYY-MM-DD):\n"
                "<i>Masalan: 2026-10-10</i>",
                parse_mode="HTML",
                reply_markup=cancel_kb("admin:schedules"),
            )
            return
        except ValueError:
            await message.answer("❌ Noto'g'ri ID. Raqam kiriting.")
            return

    # Sana tekshirish
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", text):
        await message.answer("❌ Noto'g'ri format. YYYY-MM-DD formatida kiriting.")
        return
    try:
        dt = date.fromisoformat(text)
    except ValueError:
        await message.answer("❌ Noto'g'ri sana.")
        return

    await state.update_data(start_date=text)
    await message.answer(
        "⏰ <b>4-qadam:</b> Har kungi yuborish vaqtini kiriting (HH:MM, Toshkent vaqti):\n"
        "<i>Masalan: 20:00</i>",
        parse_mode="HTML",
        reply_markup=cancel_kb("admin:schedules"),
    )
    await state.set_state(ScheduleFSM.waiting_time)


@admin_router.message(ScheduleFSM.waiting_time)
async def schedule_time(message: Message, state: FSMContext):
    import re
    text = message.text.strip()
    if not re.match(r"^\d{2}:\d{2}$", text):
        await message.answer("❌ Noto'g'ri format. HH:MM formatida kiriting (masalan: 20:00).")
        return
    h, m = text.split(":")
    if not (0 <= int(h) <= 23 and 0 <= int(m) <= 59):
        await message.answer("❌ Noto'g'ri vaqt qiymati.")
        return
    await state.update_data(send_time=text)
    await message.answer(
        "📆 <b>5-qadam:</b> Necha kun davomida yuborilsin?\n"
        "<i>Musbat butun son kiriting (masalan: 7)</i>",
        parse_mode="HTML",
        reply_markup=cancel_kb("admin:schedules"),
    )
    await state.set_state(ScheduleFSM.waiting_duration)


@admin_router.message(ScheduleFSM.waiting_duration)
async def schedule_duration(message: Message, state: FSMContext, session: AsyncSession):
    text = message.text.strip()
    try:
        days = int(text)
        if days <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Musbat butun son kiriting.")
        return

    await state.update_data(duration_days=days)
    data = await state.get_data()
    recipient = "👥 Barcha" if data["recipient_type"] == "all" else f"👤 ID: {data.get('recipient_id')}"
    preview = data.get("caption") or data.get("text") or "📎 Media"

    from datetime import date, timedelta
    start = date.fromisoformat(data["start_date"])
    end = start + timedelta(days=days - 1)

    await message.answer(
        f"📋 <b>Jadval xulasasi:</b>\n\n"
        f"📝 Xabar: {preview[:200]}\n"
        f"📬 Qabul qiluvchi: {recipient}\n"
        f"📅 Sana: {data['start_date']} → {end.isoformat()}\n"
        f"⏰ Vaqt: {data['send_time']} (Asia/Tashkent)\n"
        f"📆 Davomiylik: {days} kun\n\n"
        "Tasdiqlaysizmi?",
        parse_mode="HTML",
        reply_markup=confirm_kb("sch_confirm", "admin:schedules"),
    )
    await state.set_state(ScheduleFSM.confirm)


@admin_router.callback_query(ScheduleFSM.confirm, F.data == "sch_confirm")
async def schedule_confirm(call: CallbackQuery, session: AsyncSession, state: FSMContext):
    if not await _admin_check(call, session):
        return
    await call.answer()
    data = await state.get_data()
    await state.clear()

    sch = await crud.create_scheduled_message(
        session=session,
        text=data.get("text"),
        media_type=data.get("media_type"),
        media_file_id=data.get("file_id"),
        caption=data.get("caption"),
        recipient_type=data["recipient_type"],
        recipient_id=data.get("recipient_id"),
        start_date=data["start_date"],
        send_time=data["send_time"],
        duration_days=data["duration_days"],
        created_by=call.from_user.id,
    )
    await call.message.edit_text(
        f"✅ Jadval #{sch.id} yaratildi!\n"
        f"⏰ Birinchi yuborish: {sch.start_date} soat {sch.send_time} (Toshkent)",
        reply_markup=back_kb("admin:schedules"),
    )


# ══════════════════════════════════════════════════════════════════════════════
# YORDAMCHI FUNKSIYA — XABAR KONTENTINI AJRATIB OLISH
# ══════════════════════════════════════════════════════════════════════════════

def _extract_message_content(
    message: Message,
) -> tuple[str | None, str | None, str | None, str | None]:
    """
    Xabardan (media_type, file_id, caption, text) ni ajratadi.
    """
    if message.photo:
        return "photo", message.photo[-1].file_id, message.caption, None
    if message.video:
        return "video", message.video.file_id, message.caption, None
    if message.document:
        return "document", message.document.file_id, message.caption, None
    return None, None, None, message.text
