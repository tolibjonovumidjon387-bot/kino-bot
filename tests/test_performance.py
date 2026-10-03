"""Offline tests: Telegram calls are simulated, no real users are contacted."""
import os
import tempfile
import unittest
import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

os.environ["BOT_TOKEN"] = "123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghi"
os.environ["ADMIN_IDS"] = "123"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"

from aiogram.types import Message, Chat, CallbackQuery, User as TelegramUser
from aiogram.exceptions import TelegramForbiddenError
from aiogram.methods import GetChatMember, GetMe
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from database.models import Base, User
from database.crud import get_or_create_user
from middlewares.user_register import UserRegisterMiddleware
from handlers.admin import movies_panel, stop_bot
from handlers.user import _show_movies_page
from utils.subscription import check_user_subscription
from utils.performance import api_timing


class PerformanceTests(unittest.IsolatedAsyncioTestCase):
    async def test_channels_checked_in_parallel_and_fail_closed(self):
        running = peak = 0
        async def get_member(chat_id, user_id):
            nonlocal running, peak
            running += 1
            peak = max(peak, running)
            await asyncio.sleep(.01)
            running -= 1
            if chat_id == 7:
                raise TelegramForbiddenError(
                    method=GetChatMember(chat_id=chat_id, user_id=user_id),
                    message="Forbidden",
                )
            if chat_id == 6:
                return SimpleNamespace(status="restricted", is_member=False)
            return SimpleNamespace(status="member")
        channels = [SimpleNamespace(channel_id=i) for i in range(8)]
        ok, missing = await check_user_subscription(
            SimpleNamespace(get_chat_member=get_member), 123, channels)
        self.assertFalse(ok)
        self.assertEqual([c.channel_id for c in missing], [6, 7])
        self.assertGreater(peak, 1)
        self.assertLessEqual(peak, 4)

    async def test_restricted_member_and_empty_channels(self):
        bot = SimpleNamespace(get_chat_member=AsyncMock(
            return_value=SimpleNamespace(status="restricted", is_member=True)))
        self.assertEqual(await check_user_subscription(bot, 1, []), (True, []))
        self.assertTrue((await check_user_subscription(
            bot, 1, [SimpleNamespace(channel_id=1)]))[0])

    async def test_subscription_timeout_does_not_grant_access(self):
        bot = SimpleNamespace(get_chat_member=AsyncMock(side_effect=asyncio.TimeoutError))
        channels = [SimpleNamespace(channel_id=1)]
        self.assertEqual(await check_user_subscription(bot, 1, channels), (False, channels))

    async def test_navigation_ack_before_edit(self):
        order = []
        async def ack(*args, **kwargs): order.append("ack")
        async def edit(*args, **kwargs): order.append("edit")
        call = SimpleNamespace(from_user=SimpleNamespace(id=123),
            answer=ack, message=SimpleNamespace(edit_text=edit))
        await movies_panel(call, None)
        self.assertEqual(order, ["ack", "edit"])

    async def test_empty_category_ack_once_before_edit(self):
        order = []
        async def ack(*a, **kw): order.append("ack")
        async def edit(*a, **kw): order.append("edit")
        call = SimpleNamespace(answer=ack, message=SimpleNamespace(edit_text=edit))
        with patch("handlers.user.get_movies_by_category", AsyncMock(return_value=([], 0))):
            await _show_movies_page(call, None, None, "Multfilmlar", 0)
        self.assertEqual(order, ["ack", "edit"])

    async def test_stop_alert_not_swallowed_or_duplicated(self):
        message = Message(message_id=1, date=datetime.now(timezone.utc),
                          chat=Chat(id=123, type="private"))
        call = CallbackQuery(id="test", from_user=TelegramUser(
            id=123, is_bot=False, first_name="Test"), chat_instance="test",
            message=message, data="admin:stop_bot")
        with patch("handlers.admin.crud.set_bot_active", AsyncMock()), \
             patch("handlers.admin.crud.is_bot_active", AsyncMock(return_value=False)), \
             patch("handlers.admin.crud.count_users", AsyncMock(return_value=1)), \
             patch("handlers.admin.crud.count_movies", AsyncMock(return_value=0)), \
             patch.object(CallbackQuery, "answer", AsyncMock()) as answer, \
             patch.object(Message, "edit_text", AsyncMock()):
            await stop_bot(call, None)
        answer.assert_awaited_once()
        self.assertTrue(answer.await_args.kwargs["show_alert"])

    async def test_registration_releases_write_lock_before_handler(self):
        with tempfile.TemporaryDirectory() as tmp:
            engine = create_async_engine(f"sqlite+aiosqlite:///{tmp}/test.db",
                                         connect_args={"timeout": .2})
            factory = async_sessionmaker(engine, expire_on_commit=False)
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            message = Message(message_id=1, date=datetime.now(timezone.utc),
                chat=Chat(id=123, type="private"),
                from_user=TelegramUser(id=123, is_bot=False, first_name="Test"))
            async def handler(event, data):
                # Another update can write while this handler is still running.
                async with factory() as other:
                    other.add(User(telegram_id=456, full_name="Second"))
                    await other.commit()
                return "ok"
            try:
                async with factory() as session:
                    self.assertEqual(await UserRegisterMiddleware()(
                        handler, message, {"session": session}), "ok")
                async with factory() as session:
                    self.assertEqual(len((await session.execute(select(User))).scalars().all()), 2)
                statements = []
                def record(conn, cursor, statement, parameters, context, executemany):
                    statements.append(statement.lower())
                event.listen(engine.sync_engine, "before_cursor_execute", record)
                async with factory() as session:
                    await get_or_create_user(session, 123, None, "Test")
                self.assertFalse(any("from scheduled_send_logs" in s or
                                     "from broadcast_logs" in s for s in statements))
            finally:
                await engine.dispose()

    async def test_scheduled_batch_does_not_block_other_writers(self):
        from utils.scheduler import _send_to_users
        from database.models import ScheduledMessage
        with tempfile.TemporaryDirectory() as tmp:
            engine = create_async_engine(f"sqlite+aiosqlite:///{tmp}/scheduled.db",
                                         connect_args={"timeout": .2})
            factory = async_sessionmaker(engine, expire_on_commit=False)
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            try:
                async with factory() as session:
                    users = [User(telegram_id=1, full_name="One"),
                             User(telegram_id=2, full_name="Two")]
                    session.add_all(users)
                    await session.commit()
                    sch = SimpleNamespace(id=1, text="Test", media_type=None,
                        media_file_id=None, caption=None, parse_mode="HTML")
                    calls = 0
                    async def simulated_send(**kwargs):
                        nonlocal calls
                        calls += 1
                        if calls == 2:
                            async with factory() as other:
                                other.add(User(telegram_id=3, full_name="Independent"))
                                await other.commit()
                        return True, ""
                    with patch("utils.scheduler.safe_send_message", simulated_send):
                        await _send_to_users(None, session, sch, users, "2026-10-03")
                    self.assertEqual(calls, 2)
            finally:
                await engine.dispose()

    async def test_api_timings_safe_and_preserve_result(self):
        secret = "TOKEN_MUST_NOT_APPEAR"
        with self.assertLogs("performance", level="INFO") as logs:
            result = await api_timing(AsyncMock(return_value=42),
                                      SimpleNamespace(token=secret), GetMe())
        self.assertEqual(result, 42)
        self.assertIn("GetMe", logs.output[0])
        self.assertNotIn(secret, "".join(logs.output))


if __name__ == "__main__":
    unittest.main()
