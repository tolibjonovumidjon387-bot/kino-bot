"""One subscription gate for every matched user handler."""
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from database.crud import get_required_channels, set_setting, is_bot_active
from keyboards.user_kb import subscription_check_kb
from utils.helpers import is_admin
from utils.subscription import inspect_subscription, subscription_prompt


class SubscriptionMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        user = event.from_user
        # Admin must retain access to repair channel settings.
        if user is None or is_admin(user.id):
            return await handler(event, data)
        # Support remains reachable; this callback performs its own fresh check.
        if isinstance(event, Message) and event.text == "📩 Admin bilan bog'lanish":
            return await handler(event, data)
        if isinstance(event, CallbackQuery) and event.data == "check_subscription":
            return await handler(event, data)

        session = data["session"]
        message = event.message if isinstance(event, CallbackQuery) else event
        if not await is_bot_active(session):
            if isinstance(event, CallbackQuery):
                await event.answer("🔒 Bot vaqtincha to'xtatilgan.", show_alert=True)
            else:
                await event.answer("🔒 Bot vaqtincha to'xtatilgan.")
            return

        channels = await get_required_channels(session)
        missing, unavailable = await inspect_subscription(data["bot"], user.id, channels)
        if not missing and not unavailable:
            return await handler(event, data)

        pending = None
        if isinstance(event, CallbackQuery):
            if (event.data or "").startswith("get_movie:"):
                pending = event.data.split(":", 1)[1]
            await event.answer()
        elif event.text:
            text = event.text.strip()
            command, _, argument = text.partition(" ")
            if command.split("@", 1)[0] == "/start":
                pending = argument.strip() or None
            elif not text.startswith("/") and text not in ("🎬 Kategoriyalar", "🔍 Kino kodi"):
                pending = text
        if pending and len(pending) <= 100:
            await set_setting(session, f"pending_code:{user.id}", pending)
            await session.commit()
        if message:
            await message.answer(
                subscription_prompt(missing, unavailable),
                reply_markup=subscription_check_kb(missing + unavailable),
            )
