from aiogram import Bot, types

private_commands = [
    types.BotCommand(command="/start", description="first things first"),
    types.BotCommand(command="/settings", description="add payment requisites"),
    types.BotCommand(command="/stats", description="statistics"),
    types.BotCommand(command="/admin", description="admin section"),
    types.BotCommand(command="/info", description="bot info"),
]

group_commands: list[types.BotCommand] = []


async def set_bot_commands(bot: Bot) -> None:
    await bot.delete_my_commands(scope=types.BotCommandScopeAllPrivateChats())
    await bot.set_my_commands(
        private_commands, scope=types.BotCommandScopeAllPrivateChats()
    )
    await bot.set_my_commands(group_commands, scope=types.BotCommandScopeAllGroupChats())
    await bot.set_my_commands(group_commands, scope=types.BotCommandScopeDefault())
