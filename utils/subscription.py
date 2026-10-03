"""
Obuna tekshirish va kanal huquqlari
"""
import asyncio
import logging
from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest
from database.models import RequiredChannel

logger = logging.getLogger(__name__)


async def inspect_subscription(bot, user_id, channels):
    """Return (missing, unavailable), keeping API failures separate from non-members."""
    semaphore = asyncio.Semaphore(4)

    async def inspect(channel):
        async with semaphore:
            try:
                member = await asyncio.wait_for(
                    bot.get_chat_member(chat_id=channel.channel_id, user_id=user_id),
                    timeout=8,
                )
                status = getattr(member.status, "value", member.status)
                if status in ("member", "administrator", "creator"):
                    return "ok"
                if status == "restricted":
                    return "ok" if bool(getattr(member, "is_member", False)) else "missing"
                return "missing" if status in ("left", "kicked") else "unavailable"
            except Exception as exc:
                logger.warning("SUBSCRIPTION channel=%s error=%s",
                               channel.channel_id, type(exc).__name__)
                return "unavailable"

    results = await asyncio.gather(*(inspect(ch) for ch in channels))
    return (
        [ch for ch, result in zip(channels, results) if result == "missing"],
        [ch for ch, result in zip(channels, results) if result == "unavailable"],
    )


async def check_user_subscription(bot, user_id, channels):
    """Backward-compatible, fail-closed check."""
    missing, unavailable = await inspect_subscription(bot, user_id, channels)
    blocked_ids = {ch.channel_id for ch in missing + unavailable}
    blocked = [ch for ch in channels if ch.channel_id in blocked_ids]
    return not blocked, blocked


def subscription_prompt(missing, unavailable):
    if unavailable:
        return (
            "⚠️ Obunani hozir tekshirib bo'lmadi.\n"
            "Birozdan keyin «Obunani tekshirish» tugmasini bosing.\n"
            "Muammo davom etsa, admin botning kanalda administrator "
            "ekanini va kanal ID sini tekshirsin.\n"
            "Tasdiq olinmaguncha botdan foydalanish cheklangan."
        )
    return (
        "📢 <b>Botdan foydalanish uchun quyidagi kanallarga a'zo bo'ling:</b>\n\n"
        "A'zo bo'lgach, «✅ Obunani tekshirish» tugmasini bosing.\n"
        "Kanalga kirish so'rovi yuborilgan bo'lsa, u tasdiqlanishi kerak."
    )


async def check_bot_channel_rights(bot: Bot, channel_id: int) -> tuple[bool, str]:
    """
    Botning kanalda zaruriy huquqlari borligini tekshiradi.
    (ok, xato_xabari) qaytaradi.
    """
    try:
        bot_info = await bot.get_me()
        member = await bot.get_chat_member(
            chat_id=channel_id, user_id=bot_info.id
        )
        status = member.status.value if hasattr(member.status, "value") else str(member.status)
        if status not in ("administrator", "creator"):
            return False, (
                f"❌ Bot kanalda administrator emas (holat: {status}).\n"
                "Botni kanalga admin sifatida qo'shing."
            )
        return True, ""
    except TelegramForbiddenError:
        return False, (
            "❌ Bot kanalga kirish huquqiga ega emas.\n"
            "Botni kanalga admin sifatida qo'shing."
        )
    except TelegramBadRequest as e:
        return False, f"❌ Kanal topilmadi yoki noto'g'ri ID: {e}"
    except Exception as e:
        return False, f"❌ Kutilmagan xato: {e}"
