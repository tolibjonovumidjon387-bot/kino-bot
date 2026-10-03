"""
Telegram Kino Bot — asosiy ishga tushirish fayli
"""
import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN
from database import init_db
from handlers import user_router, admin_router
from middlewares import DbSessionMiddleware, UserRegisterMiddleware
from utils.scheduler import start_scheduler, mark_missed_sends
from utils.performance import UpdateTimingMiddleware, api_timing

# ─── Logging sozlamasi ────────────────────────────────────────────────────── #
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("bot.log", encoding="utf-8"),
    ],
)
# Maxfiy tokenni loglarga chiqarmaslik
logging.getLogger("aiogram").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


async def main():
    logger.info("Bot ishga tushmoqda...")

    # Ma'lumotlar bazasini tayyorlash
    await init_db()
    logger.info("Baza tayyor.")

    # Bot va Dispatcher
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    bot.session.middleware(api_timing)
    dp = Dispatcher(storage=MemoryStorage())
    dp.update.outer_middleware(UpdateTimingMiddleware())

    # Middleware'larni ro'yxatdan o'tkazish
    # Tartib muhim: avval DB sessiyasi, keyin foydalanuvchi
    dp.message.middleware(DbSessionMiddleware())
    dp.callback_query.middleware(DbSessionMiddleware())
    dp.message.middleware(UserRegisterMiddleware())
    dp.callback_query.middleware(UserRegisterMiddleware())

    # Routerlarni ulash
    dp.include_router(admin_router)   # admin oldin (priority)
    dp.include_router(user_router)

    # O'tkazib yuborilgan jadvallarni belgilash
    try:
        await mark_missed_sends(bot)
    except Exception as e:
        logger.error("Missed sends belgilashda xato: %s", e)

    # Schedulerni ishga tushirish
    start_scheduler(bot)
    logger.info("Scheduler ishga tushdi.")

    # Polling boshlash
    logger.info("Polling boshlandi. To'xtatish uchun Ctrl+C bosing.")
    try:
        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types(),
            drop_pending_updates=True,
        )
    finally:
        logger.info("Bot to'xtatilmoqda...")
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot to'xtatildi.")
