"""
Rejalashtirilgan xabarlar scheduler moduli.
APScheduler (AsyncIOScheduler) ishlatiladi.
Har daqiqa aktiv jadvallar tekshiriladi va vaqt to'g'ri kelsa yuboriladi.

Takrordan himoya: ScheduledSendLog jadvalidagi
(schedule_id, user_id, send_date) noyob indeksi orqali.

Restart siyosati:
- Bot o'chib qolgan paytdagi o'tkazib yuborilganlar
  YUBORILMAYDI, "skipped" deb belgilanadi va adminga xabar beriladi.
- "exactly once" kafolati: DB darajasida UNIQUE constraint bilan ta'minlanadi.
  Parallel worker bo'lsa IntegrityError yuz beradi va qayta urinilmaydi.
"""
import asyncio
import logging
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import ADMIN_IDS, TIMEZONE
from database.crud import (
    get_active_schedules, get_all_active_users,
    get_user_by_telegram_id, is_already_sent,
    log_scheduled_send, update_schedule_status,
    is_bot_active,
)
from database.engine import AsyncSessionLocal
from database.models import ScheduledMessage, User
from utils.helpers import safe_send_message

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


def get_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler(timezone=TIMEZONE)
    return _scheduler


def start_scheduler(bot: Bot):
    """Schedulerni ishga tushiradi."""
    scheduler = get_scheduler()
    # Har daqiqa tekshirish (vaqt aniqligi: ±1 daqiqa)
    scheduler.add_job(
        _check_and_send_scheduled,
        trigger="cron",
        minute="*",
        id="scheduled_check",
        replace_existing=True,
        kwargs={"bot": bot},
    )
    if not scheduler.running:
        scheduler.start()
    logger.info("Scheduler ishga tushirildi.")


def stop_scheduler():
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
    logger.info("Scheduler to'xtatildi.")


async def _check_and_send_scheduled(bot: Bot):
    """
    Har daqiqa chaqiriladi.
    Aktiv jadvallarni ko'rib chiqadi va bugungi yuborishlarni amalga oshiradi.
    """
    tz = ZoneInfo(TIMEZONE)
    now = datetime.now(tz)
    today_str = now.strftime("%Y-%m-%d")
    current_time = now.strftime("%H:%M")

    async with AsyncSessionLocal() as session:
        # Bot to'xtatilgan bo'lsa yuborilmaydi
        bot_active = await is_bot_active(session)
        if not bot_active:
            return

        schedules = await get_active_schedules(session)

    for sch in schedules:
        # Jadval uchun vaqt to'g'ri kelayaptimi?
        if sch.send_time != current_time:
            continue

        async with AsyncSessionLocal() as session:
            await _process_schedule(bot, session, sch, today_str)


async def _process_schedule(
    bot: Bot,
    session,
    sch: ScheduledMessage,
    today_str: str,
):
    """
    Bitta jadval uchun bugungi yuborishni amalga oshiradi.
    """
    tz = ZoneInfo(TIMEZONE)
    today = date.fromisoformat(today_str)

    # Boshlanish sanasini tekshirish
    start = date.fromisoformat(sch.start_date)
    if today < start:
        return  # Hali boshlanmagan

    # Tugash sanasini hisoblash
    end = start + timedelta(days=sch.duration_days - 1)
    if today > end:
        # Jadval tugagan — holati yangilanadi
        await update_schedule_status(session, sch.id, "finished")
        await session.commit()
        logger.info("Jadval #%s tugadi.", sch.id)
        return

    # Qabul qiluvchilarni aniqlash
    if sch.recipient_type == "all":
        users = await get_all_active_users(session)
        await _send_to_users(bot, session, sch, users, today_str)
    else:
        user = await get_user_by_telegram_id(session, sch.recipient_id)
        if user:
            await _send_to_users(bot, session, sch, [user], today_str)
        else:
            logger.warning("Jadval #%s: foydalanuvchi %s topilmadi.", sch.id, sch.recipient_id)

    await session.commit()


async def _send_to_users(
    bot: Bot,
    session,
    sch: ScheduledMessage,
    users: list[User],
    today_str: str,
):
    from config import BROADCAST_DELAY
    for user in users:
        # Takrordan himoya
        already = await is_already_sent(session, sch.id, user.id, today_str)
        if already:
            continue

        ok, err = await safe_send_message(
            bot=bot,
            chat_id=user.telegram_id,
            text=sch.text,
            media_type=sch.media_type,
            media_file_id=sch.media_file_id,
            caption=sch.caption,
            parse_mode=sch.parse_mode or "HTML",
        )

        status = "sent" if ok else ("blocked" if err == "blocked" else "failed")
        error_text = None if ok else err

        try:
            await log_scheduled_send(
                session=session,
                schedule_id=sch.id,
                user_db_id=user.id,
                send_date=today_str,
                status=status,
                error_text=error_text,
            )
            await session.commit()
        except Exception as e:
            await session.rollback()
            # IntegrityError: parallel yuborishdan himoya
            logger.warning("Jadval log xato (parallel?): %s", e)
            raise

        if "retry_after:" in str(err):
            try:
                wait = int(str(err).split(":")[1])
                await asyncio.sleep(wait)
            except Exception:
                await asyncio.sleep(30)
        else:
            await asyncio.sleep(BROADCAST_DELAY)


async def mark_missed_sends(bot: Bot):
    """
    Bot qayta ishga tushganda o'tkazib yuborilgan
    jadval yuborishlarini "skipped" deb belgilaydi
    va adminga xabar yuboradi.
    """
    tz = ZoneInfo(TIMEZONE)
    now = datetime.now(tz)
    today_str = now.strftime("%Y-%m-%d")
    today = date.fromisoformat(today_str)

    async with AsyncSessionLocal() as session:
        schedules = await get_active_schedules(session)
        missed_info = []

        for sch in schedules:
            start = date.fromisoformat(sch.start_date)
            end = start + timedelta(days=sch.duration_days - 1)

            # O'tgan kunlar (bugun emas)
            check_date = max(start, today - timedelta(days=7))  # oxirgi 7 kun
            while check_date < today and check_date <= end:
                date_str = check_date.strftime("%Y-%m-%d")

                if sch.recipient_type == "all":
                    users = await get_all_active_users(session)
                    for user in users:
                        already = await is_already_sent(session, sch.id, user.id, date_str)
                        if not already:
                            try:
                                await log_scheduled_send(
                                    session, sch.id, user.id, date_str, "skipped",
                                    "Bot o'chib qolgan paytda o'tkazib yuborildi"
                                )
                                missed_info.append(f"Jadval #{sch.id} - {date_str}")
                            except Exception:
                                pass

                check_date += timedelta(days=1)

        await session.commit()

        if missed_info:
            unique_missed = list(set(missed_info))
            msg = (
                "⚠️ <b>O'tkazib yuborilgan jadvallar:</b>\n" +
                "\n".join(f"• {m}" for m in unique_missed[:20])
            )
            for admin_id in ADMIN_IDS:
                try:
                    await bot.send_message(admin_id, msg, parse_mode="HTML")
                except Exception:
                    pass
