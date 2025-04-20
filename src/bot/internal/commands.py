from aiogram import Bot, types

default_commands = [
    types.BotCommand(command="/start", description="first things first"),
    types.BotCommand(command="/info", description="get some info"),
    types.BotCommand(command="/admin", description="admin section"),
]


async def set_bot_commands(bot: Bot) -> None:
    await bot.set_my_commands(default_commands)
