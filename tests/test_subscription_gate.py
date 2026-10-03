"""Real dispatcher + temporary SQLite + simulated Telegram; no network calls."""
import os
os.environ["BOT_TOKEN"] = "123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghi"
os.environ["ADMIN_IDS"] = "123"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"

import tempfile
import unittest
from datetime import datetime, timezone
from unittest.mock import patch
from aiogram import Bot, Dispatcher
from aiogram.client.session.base import BaseSession
from aiogram.types import (
    Update, Message, Chat, User, CallbackQuery, ChatMemberMember,
    ChatMemberLeft, MessageId,
)
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from database.models import Base, RequiredChannel, Movie
from handlers.user import user_router
from middlewares import DbSessionMiddleware, UserRegisterMiddleware


class TelegramStub(BaseSession):
    def __init__(self):
        super().__init__()
        self.status = "left"
        self.calls = []

    async def close(self):
        pass

    async def stream_content(self, *args, **kwargs):
        if False:
            yield b""

    async def make_request(self, bot, method, timeout=None):
        self.calls.append(method)
        name = type(method).__name__
        if name == "GetChatMember":
            if self.status == "error":
                raise TimeoutError("simulated")
            user = User(id=method.user_id, is_bot=False, first_name="Viewer")
            cls = ChatMemberMember if self.status == "member" else ChatMemberLeft
            return cls(user=user)
        if name == "CopyMessage":
            return MessageId(message_id=99)
        if name == "SendMessage":
            return Message(message_id=99, date=datetime.now(timezone.utc),
                chat=Chat(id=method.chat_id, type="private"), text=method.text)
        return True


class GateIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_all_entry_points_recheck_and_resume_pending_movie(self):
        with tempfile.TemporaryDirectory() as tmp:
            engine = create_async_engine(f"sqlite+aiosqlite:///{tmp}/gate.db")
            factory = async_sessionmaker(engine, expire_on_commit=False)
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            async with factory() as db:
                db.add(RequiredChannel(channel_id=-1001, channel_title="Required",
                    invite_link="https://t.me/example"))
                db.add(Movie(code="001", title="Film", category="Multfilmlar",
                    channel_id=-1002, message_id=10))
                await db.commit()
            api = TelegramStub()
            bot = Bot(token=os.environ["BOT_TOKEN"], session=api)
            dp = Dispatcher()
            for observer in (dp.message, dp.callback_query):
                observer.middleware(DbSessionMiddleware())
                observer.middleware(UserRegisterMiddleware())
            dp.include_router(user_router)
            update_id = 0

            async def dispatch(text=None, callback=None, uid=456):
                nonlocal update_id
                update_id += 1
                api.calls.clear()
                user = User(id=uid, is_bot=False, first_name="Viewer")
                message = Message(message_id=update_id, date=datetime.now(timezone.utc),
                                  from_user=user, chat=Chat(id=uid, type="private"),
                                  text=text or "Old menu")
                if callback is None:
                    update = Update(update_id=update_id, message=message)
                else:
                    update = Update(update_id=update_id, callback_query=CallbackQuery(
                        id=str(update_id), from_user=user, message=message,
                        chat_instance="test", data=callback))
                await dp.feed_update(bot, update)
                return list(api.calls)

            try:
                with patch("middlewares.db.AsyncSessionLocal", factory):
                    # Every user entry point blocks non-members, including stale buttons.
                    for kwargs in (
                        {"text": "/start"}, {"text": "🎬 Kategoriyalar"},
                        {"text": "🔍 Kino kodi"}, {"text": "001"},
                        {"text": "/start 001"}, {"callback": "cat:Multfilmlar"},
                        {"callback": "cat_page:Multfilmlar:0"},
                        {"callback": "back_to_categories"}, {"callback": "noop"},
                        {"callback": "get_movie:001"},
                    ):
                        with self.subTest(kwargs=kwargs):
                            calls = await dispatch(**kwargs)
                            self.assertFalse(any(type(c).__name__ == "CopyMessage" for c in calls))
                            self.assertTrue(any(type(c).__name__ == "SendMessage"
                                and "a'zo bo'ling" in c.text for c in calls))

                    # A false membership confirmation must not send the saved film.
                    calls = await dispatch(callback="check_subscription")
                    self.assertFalse(any(type(c).__name__ == "CopyMessage" for c in calls))

                    # Joining + explicit recheck sends saved film after exactly one fresh check.
                    api.status = "member"
                    calls = await dispatch(callback="check_subscription")
                    self.assertEqual(sum(type(c).__name__ == "GetChatMember" for c in calls), 1)
                    self.assertEqual(sum(type(c).__name__ == "CopyMessage" for c in calls), 1)
                    # Saved code was cleared, so checking again does not resend the film.
                    calls = await dispatch(callback="check_subscription")
                    self.assertFalse(any(type(c).__name__ == "CopyMessage" for c in calls))
                    self.assertTrue(any(type(c).__name__ == "SendMessage" and
                                        c.reply_markup is not None for c in calls))
                    calls = await dispatch(text="001")
                    self.assertTrue(any(type(c).__name__ == "CopyMessage" for c in calls))

                    # Leaving invalidates access immediately; no membership cache.
                    api.status = "left"
                    calls = await dispatch(callback="get_movie:001")
                    self.assertFalse(any(type(c).__name__ == "CopyMessage" for c in calls))

                    # Network failure is fail-closed, with an accurate technical message.
                    api.status = "error"
                    for kwargs in ({"text": "/start"}, {"callback": "check_subscription"}):
                        calls = await dispatch(**kwargs)
                        self.assertTrue(any(type(c).__name__ == "SendMessage" and
                            "tekshirib bo'lmadi" in c.text for c in calls))
                        self.assertFalse(any(type(c).__name__ == "CopyMessage" for c in calls))

                    # Admin and support exemptions are intentional, without API lookups.
                    calls = await dispatch(text="/start", uid=123)
                    self.assertFalse(any(type(c).__name__ == "GetChatMember" for c in calls))
                    calls = await dispatch(text="📩 Admin bilan bog'lanish")
                    self.assertFalse(any(type(c).__name__ == "GetChatMember" for c in calls))
            finally:
                await dp.storage.close()
                await bot.session.close()
                await engine.dispose()
