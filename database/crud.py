"""
Ma'lumotlar bazasi CRUD operatsiyalari
"""
import logging
from datetime import datetime
from typing import Optional
from sqlalchemy import select, update, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import noload

from .models import (
    User, Movie, RequiredChannel, BotSetting,
    ScheduledMessage, ScheduledSendLog, BroadcastLog
)

logger = logging.getLogger(__name__)

# ─────────────────────────── FOYDALANUVCHILAR ────────────────────────────── #

async def get_or_create_user(
    session: AsyncSession,
    telegram_id: int,
    username: Optional[str],
    full_name: str,
) -> tuple[User, bool]:
    """Foydalanuvchini topadi yoki yangi yaratadi. (user, created) qaytaradi."""
    result = await session.execute(
        select(User).options(noload(User.broadcast_logs), noload(User.scheduled_logs)).where(User.telegram_id == telegram_id)
    )
    user = result.scalar_one_or_none()
    if user:
        changed = False
        if user.username != username:
            user.username = username
            changed = True
        if user.full_name != full_name:
            user.full_name = full_name
            changed = True
        if user.is_blocked:
            user.is_blocked = False
            changed = True
        if changed:
            await session.flush()
        return user, False
    user = User(telegram_id=telegram_id, username=username, full_name=full_name)
    session.add(user)
    await session.flush()
    return user, True


async def get_user_by_telegram_id(session: AsyncSession, telegram_id: int) -> Optional[User]:
    result = await session.execute(
        select(User).options(noload(User.broadcast_logs), noload(User.scheduled_logs)).where(User.telegram_id == telegram_id)
    )
    return result.scalar_one_or_none()


async def get_user_by_username(session: AsyncSession, username: str) -> Optional[User]:
    clean = username.lstrip("@").lower()
    result = await session.execute(
        select(User).where(func.lower(User.username) == clean)
    )
    return result.scalar_one_or_none()


async def mark_user_blocked(session: AsyncSession, telegram_id: int):
    await session.execute(
        update(User).where(User.telegram_id == telegram_id).values(is_blocked=True)
    )
    await session.flush()


async def get_all_active_users(session: AsyncSession) -> list[User]:
    result = await session.execute(
        select(User).where(User.is_blocked == False)
    )
    return list(result.scalars().all())


async def count_users(session: AsyncSession) -> int:
    result = await session.execute(select(func.count()).select_from(User))
    return result.scalar_one()


# ─────────────────────────────── KINOLAR ─────────────────────────────────── #

async def add_movie(
    session: AsyncSession,
    code: str,
    title: str,
    category: str,
    channel_id: int,
    message_id: int,
    added_by: int,
) -> tuple[Optional[Movie], str]:
    """Yangi kino qo'shadi. (movie, error_msg) qaytaradi."""
    # Kod takrorlanishini tekshirish
    existing = await session.execute(
        select(Movie).where(Movie.code == code)
    )
    if existing.scalar_one_or_none():
        return None, f"❌ '{code}' kodi allaqachon mavjud!"

    movie = Movie(
        code=code,
        title=title,
        category=category,
        channel_id=channel_id,
        message_id=message_id,
        added_by=added_by,
    )
    session.add(movie)
    await session.flush()
    return movie, ""


async def get_movie_by_code(session: AsyncSession, code: str) -> Optional[Movie]:
    result = await session.execute(
        select(Movie).where(Movie.code == code)
    )
    return result.scalar_one_or_none()


async def get_movies_by_category(
    session: AsyncSession, category: str, offset: int = 0, limit: int = 10
) -> tuple[list[Movie], int]:
    """(kinolar, jami_soni) qaytaradi"""
    total_q = await session.execute(
        select(func.count()).select_from(Movie).where(Movie.category == category)
    )
    total = total_q.scalar_one()

    result = await session.execute(
        select(Movie)
        .where(Movie.category == category)
        .order_by(Movie.title)
        .offset(offset)
        .limit(limit)
    )
    return list(result.scalars().all()), total


async def update_movie(
    session: AsyncSession,
    movie_id: int,
    **kwargs,
) -> bool:
    kwargs["updated_at"] = datetime.utcnow()
    result = await session.execute(
        update(Movie).where(Movie.id == movie_id).values(**kwargs)
    )
    await session.flush()
    return result.rowcount > 0


async def delete_movie(session: AsyncSession, code: str) -> bool:
    result = await session.execute(
        delete(Movie).where(Movie.code == code)
    )
    await session.flush()
    return result.rowcount > 0


async def count_movies(session: AsyncSession) -> int:
    result = await session.execute(select(func.count()).select_from(Movie))
    return result.scalar_one()


# ──────────────────────── MAJBURIY KANALLAR ──────────────────────────────── #

async def get_required_channels(session: AsyncSession) -> list[RequiredChannel]:
    result = await session.execute(
        select(RequiredChannel).where(RequiredChannel.is_active == True)
    )
    return list(result.scalars().all())


async def add_required_channel(
    session: AsyncSession,
    channel_id: int,
    channel_title: str,
    invite_link: str,
) -> tuple[Optional[RequiredChannel], str]:
    existing = await session.execute(
        select(RequiredChannel).where(RequiredChannel.channel_id == channel_id)
    )
    ch = existing.scalar_one_or_none()
    if ch:
        if not ch.is_active:
            ch.is_active = True
            ch.channel_title = channel_title
            ch.invite_link = invite_link
            await session.flush()
            return ch, ""
        return None, "❌ Bu kanal allaqachon ro'yxatda mavjud."

    ch = RequiredChannel(
        channel_id=channel_id,
        channel_title=channel_title,
        invite_link=invite_link,
    )
    session.add(ch)
    await session.flush()
    return ch, ""


async def remove_required_channel(session: AsyncSession, channel_id: int) -> bool:
    result = await session.execute(
        update(RequiredChannel)
        .where(RequiredChannel.channel_id == channel_id)
        .values(is_active=False)
    )
    await session.flush()
    return result.rowcount > 0


# ─────────────────────────── BOT SOZLAMALARI ─────────────────────────────── #

async def get_setting(session: AsyncSession, key: str, default: str = "") -> str:
    result = await session.execute(
        select(BotSetting).where(BotSetting.key == key)
    )
    row = result.scalar_one_or_none()
    return row.value if row else default


async def set_setting(session: AsyncSession, key: str, value: str):
    result = await session.execute(
        select(BotSetting).where(BotSetting.key == key)
    )
    row = result.scalar_one_or_none()
    if row:
        row.value = value
        row.updated_at = datetime.utcnow()
    else:
        session.add(BotSetting(key=key, value=value))
    await session.flush()


async def is_bot_active(session: AsyncSession) -> bool:
    val = await get_setting(session, "bot_active", "1")
    return val == "1"


async def set_bot_active(session: AsyncSession, active: bool):
    await set_setting(session, "bot_active", "1" if active else "0")


async def get_admin_contact(session: AsyncSession, default: str = "") -> str:
    return await get_setting(session, "admin_contact", default)


async def set_admin_contact(session: AsyncSession, username: str):
    await set_setting(session, "admin_contact", username.lstrip("@"))


# ─────────────────────── REJALASHTIRILGAN XABARLAR ───────────────────────── #

async def create_scheduled_message(
    session: AsyncSession,
    **kwargs,
) -> ScheduledMessage:
    msg = ScheduledMessage(**kwargs)
    session.add(msg)
    await session.flush()
    return msg


async def get_active_schedules(session: AsyncSession) -> list[ScheduledMessage]:
    result = await session.execute(
        select(ScheduledMessage).where(ScheduledMessage.status == "active")
    )
    return list(result.scalars().all())


async def get_all_schedules(session: AsyncSession) -> list[ScheduledMessage]:
    result = await session.execute(
        select(ScheduledMessage).order_by(ScheduledMessage.created_at.desc())
    )
    return list(result.scalars().all())


async def get_schedule_by_id(session: AsyncSession, schedule_id: int) -> Optional[ScheduledMessage]:
    result = await session.execute(
        select(ScheduledMessage).where(ScheduledMessage.id == schedule_id)
    )
    return result.scalar_one_or_none()


async def update_schedule_status(
    session: AsyncSession, schedule_id: int, status: str
):
    await session.execute(
        update(ScheduledMessage)
        .where(ScheduledMessage.id == schedule_id)
        .values(status=status)
    )
    await session.flush()


async def is_already_sent(
    session: AsyncSession,
    schedule_id: int,
    user_db_id: Optional[int],
    send_date: str,
) -> bool:
    """Takrordan himoya: bu foydalanuvchiga bugun yuborilganmi?"""
    q = select(ScheduledSendLog).where(
        ScheduledSendLog.schedule_id == schedule_id,
        ScheduledSendLog.user_id == user_db_id,
        ScheduledSendLog.send_date == send_date,
        ScheduledSendLog.status == "sent",
    )
    result = await session.execute(q)
    return result.scalar_one_or_none() is not None


async def log_scheduled_send(
    session: AsyncSession,
    schedule_id: int,
    user_db_id: Optional[int],
    send_date: str,
    status: str,
    error_text: Optional[str] = None,
):
    log = ScheduledSendLog(
        schedule_id=schedule_id,
        user_id=user_db_id,
        send_date=send_date,
        status=status,
        error_text=error_text,
    )
    session.add(log)
    await session.flush()


# ──────────────────────── BROADCAST LOG ──────────────────────────────────── #

async def log_broadcast(
    session: AsyncSession,
    broadcast_id: str,
    user_db_id: Optional[int],
    status: str,
    error_text: Optional[str] = None,
):
    log = BroadcastLog(
        broadcast_id=broadcast_id,
        user_id=user_db_id,
        status=status,
        error_text=error_text,
    )
    session.add(log)
    await session.flush()
