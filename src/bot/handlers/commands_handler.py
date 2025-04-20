from aiogram import Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import Settings
from bot.controllers.game import get_active_game
from bot.internal.dicts import texts
from bot.internal.enums import GameStatus
from bot.internal.keyboards import game_menu_kb

from database.models import User


router = Router()


@router.message(CommandStart())
async def command_handler(
    message: Message,
    command: CommandObject,
    user: User,
    settings: Settings,
    db_session: AsyncSession,
) -> None:
    await message.answer(
        text=f"hey, {user.fullname}",
    )


@router.message(Command("admin"))
async def admin_command(
    message: Message, user: User, state: FSMContext, db_session: AsyncSession
) -> None:
    if not user.is_admin:
        await message.answer(text=texts["insufficient_privileges"])
        return
    game = await get_active_game(db_session)
    status = GameStatus.ACTIVE if game else None
    await message.answer(
        text=texts["admin_menu"], reply_markup=game_menu_kb(status=status)
    )
