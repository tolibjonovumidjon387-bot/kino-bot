"""
Har bir xabarda foydalanuvchini ro'yxatga oladi / ma'lumotlarini yangilaydi.
"""
import logging
from time import perf_counter
from typing import Any, Awaitable, Callable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession
from database.crud import get_or_create_user


logger = logging.getLogger("performance")


class UserRegisterMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        session: AsyncSession = data.get("session")
        user = None

        if isinstance(event, Message):
            user = event.from_user
        elif isinstance(event, CallbackQuery):
            user = event.from_user

        if user and session:
            started = perf_counter()
            db_user, _ = await get_or_create_user(
                session=session,
                telegram_id=user.id,
                username=user.username,
                full_name=user.full_name,
            )
            await session.commit()  # Telegramni kutishda yozuv qulfi qolmasin.
            logger.info("DB_REGISTER duration=%.3fs", perf_counter() - started)
            data["db_user"] = db_user

        return await handler(event, data)
