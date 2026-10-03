"""
Yordamchi funksiyalar
"""
import logging
from aiogram import Bot
from aiogram.exceptions import (
    TelegramForbiddenError, TelegramBadRequest, TelegramRetryAfter
)
from config import ADMIN_IDS
from database.models import Movie

logger = logging.getLogger(__name__)


def is_admin(user_id: int) -> bool:
    """Foydalanuvchi admin ekanligini tekshiradi."""
    return user_id in ADMIN_IDS


def format_movie_info(movie: Movie) -> str:
    return (
        f"🎬 <b>{movie.title}</b>\n"
        f"🔑 Kod: <code>{movie.code}</code>\n"
        f"📂 Kategoriya: {movie.category}"
    )


async def safe_send_message(
    bot: Bot,
    chat_id: int,
    text: str | None = None,
    media_type: str | None = None,
    media_file_id: str | None = None,
    caption: str | None = None,
    parse_mode: str = "HTML",
) -> tuple[bool, str]:
    """
    Xabarni xavfsiz yuboradi.
    (muvaffaqiyat, xato_xabari) qaytaradi.
    """
    try:
        if media_type == "photo" and media_file_id:
            await bot.send_photo(
                chat_id=chat_id,
                photo=media_file_id,
                caption=caption,
                parse_mode=parse_mode,
            )
        elif media_type == "video" and media_file_id:
            await bot.send_video(
                chat_id=chat_id,
                video=media_file_id,
                caption=caption,
                parse_mode=parse_mode,
            )
        elif media_type == "document" and media_file_id:
            await bot.send_document(
                chat_id=chat_id,
                document=media_file_id,
                caption=caption,
                parse_mode=parse_mode,
            )
        else:
            if text:
                await bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    parse_mode=parse_mode,
                )
        return True, ""
    except TelegramForbiddenError:
        return False, "blocked"
    except TelegramBadRequest as e:
        return False, str(e)
    except TelegramRetryAfter as e:
        return False, f"retry_after:{e.retry_after}"
    except Exception as e:
        return False, str(e)


async def forward_movie_to_user(
    bot: Bot,
    user_id: int,
    from_chat_id: int,
    message_id: int,
) -> tuple[bool, str]:
    """
    Arxiv kanalidan kinoni foydalanuvchiga forward qiladi.
    (ok, xato) qaytaradi.
    """
    try:
        await bot.copy_message(
            chat_id=user_id,
            from_chat_id=from_chat_id,
            message_id=message_id,
        )
        return True, ""
    except TelegramForbiddenError:
        return False, "blocked"
    except TelegramBadRequest as e:
        msg = str(e)
        if "message to copy not found" in msg.lower():
            return False, "not_found"
        return False, msg
    except Exception as e:
        return False, str(e)
