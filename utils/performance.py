"""Safe timings: never log tokens, URLs, message bodies or callback payloads."""
import logging
from time import perf_counter
from aiogram import BaseMiddleware

logger = logging.getLogger("performance")


class UpdateTimingMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        started = perf_counter()
        kind = "callback" if getattr(event, "callback_query", None) else "message"
        try:
            return await handler(event, data)
        finally:
            logger.info("UPDATE id=%s type=%s duration=%.3fs",
                        getattr(event, "update_id", "?"), kind,
                        perf_counter() - started)


async def api_timing(make_request, bot, method):
    started = perf_counter()
    outcome = "ok"
    try:
        return await make_request(bot, method)
    except Exception as exc:
        outcome = type(exc).__name__
        raise
    finally:
        # Long polling normally waits. It is not a slow button request.
        if type(method).__name__ != "GetUpdates":
            logger.info("API method=%s duration=%.3fs result=%s",
                        type(method).__name__, perf_counter() - started, outcome)
