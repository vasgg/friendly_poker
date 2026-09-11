import logging
from asyncio import CancelledError, run
from contextlib import suppress

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage, SimpleEventIsolation

from bot.config import settings
from bot.handlers.callbacks import router as callbacks_router
from bot.handlers.commands_handler import router as command_router
from bot.handlers.debt_handlers import router as debts_router
from bot.handlers.errors_handler import router as errors_router
from bot.handlers.photo_handler import router as photo_router
from bot.handlers.states_handler import router as states_router
from bot.internal.commands import set_bot_commands
from bot.internal.config_dicts import initial_setup
from bot.internal.notify_admin import on_shutdown, on_startup
from bot.internal.poll import start_weekly_poll_loop
from bot.middlewares.auth_middleware import AuthMiddleware
from bot.middlewares.logging_middleware import LoggingMiddleware
from bot.middlewares.session_middleware import DBSessionMiddleware
from bot.middlewares.updates_dumper_middleware import UpdatesDumperMiddleware
from database.database_connector import get_db


async def main():
    bot = Bot(
        token=settings.bot.TOKEN.get_secret_value(),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    storage = MemoryStorage()
    dispatcher = Dispatcher(
        events_isolation=SimpleEventIsolation(), storage=storage, settings=settings
    )
    db = get_db()

    async def dispose_db(*_: object, **__: object) -> None:
        await db.dispose()
        logging.info("Database connection pool disposed")

    dispatcher.update.outer_middleware(UpdatesDumperMiddleware())
    dispatcher.startup.register(on_startup)
    dispatcher.shutdown.register(on_shutdown)
    dispatcher.shutdown.register(dispose_db)
    dispatcher.startup.register(set_bot_commands)
    db_session_middleware = DBSessionMiddleware(db)
    dispatcher.message.middleware(db_session_middleware)
    dispatcher.callback_query.middleware(db_session_middleware)
    dispatcher.message.middleware(AuthMiddleware())
    dispatcher.callback_query.middleware(AuthMiddleware())
    dispatcher.message.middleware.register(LoggingMiddleware())
    dispatcher.callback_query.middleware.register(LoggingMiddleware())
    dispatcher.include_routers(
        command_router,
        callbacks_router,
        errors_router,
        states_router,
        debts_router,
        photo_router,
    )

    logging.info("friendly poker bot started")
    poll_task = start_weekly_poll_loop(bot, settings.bot.GROUP_ID)
    try:
        await dispatcher.start_polling(bot, close_bot_session=False)
    finally:
        # Finish the background request before closing its HTTP session.
        poll_task.cancel()
        try:
            with suppress(CancelledError):
                await poll_task
        finally:
            await bot.session.close()


def run_main():
    listeners = initial_setup("friendly_poker_bot")
    try:
        run(main())
    finally:
        for listener in listeners:
            listener.stop()


if __name__ == "__main__":
    run_main()
