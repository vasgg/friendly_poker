from asyncio import run
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from bot.middlewares.auth_middleware import AuthMiddleware
from bot.middlewares.logging_middleware import LoggingMiddleware
from bot.internal.commands import set_bot_commands
from bot.internal.notify_admin import on_shutdown, on_startup
from bot.middlewares.session_middleware import DBSessionMiddleware
from bot.middlewares.updates_dumper_middleware import UpdatesDumperMiddleware
from bot.handlers.commands_handler import router as command_router
from bot.handlers.states_handler import router as states_router
from bot.handlers.debt_handlers import router as debts_router
from bot.handlers.callbacks_handlers import router as callbacks_router
from bot.handlers.errors_handler import router as errors_router
from bot.internal.config_dicts import setup_logs_and_more

from bot.config import settings
from database.database_connector import get_db


async def main():
    setup_logs_and_more("friendly_poker_bot")

    bot = Bot(
        token=settings.bot.TOKEN.get_secret_value(),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    storage = MemoryStorage()
    dispatcher = Dispatcher(storage=storage, settings=settings)
    db = get_db()

    dispatcher.update.outer_middleware(UpdatesDumperMiddleware())
    dispatcher.startup.register(on_startup)
    dispatcher.shutdown.register(on_shutdown)
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
    )

    await dispatcher.start_polling(bot)
    logging.info("friendly poker bot started")


def run_main():
    run(main())


if __name__ == "__main__":
    run_main()
