from aiogram import Bot, types

default_commands = [
    types.BotCommand(command="/start", description="first things first"),
    types.BotCommand(command="/settings", description="add payment requisites"),
    types.BotCommand(command="/stats", description="statistics"),
    types.BotCommand(command="/admin", description="admin section"),
]


async def set_bot_commands(bot: Bot) -> None:
    await bot.set_my_commands(default_commands)
