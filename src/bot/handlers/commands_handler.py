from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import NoResultFound

from bot.controllers.game import (
    games_hosting_count,
    games_playing_count,
    get_active_game,
    get_mvp_count,
    get_player_total_buy_in,
    get_player_total_buy_out,
)
from bot.controllers.record import get_record
from bot.internal.lexicon import ORDER, SETTINGS_QUESTIONS, texts
from bot.internal.context import GameStatus, SettingsForm
from bot.internal.keyboards import game_menu_kb

from database.models import User


router = Router()


@router.message(CommandStart())
async def command_handler(
    message: Message,
    user: User,
) -> None:
    await message.answer(
        text=f"hey, {user.fullname}",
    )


@router.message(Command("admin"))
async def admin_command(message: Message, user: User, db_session: AsyncSession, state: FSMContext, settings) -> None:
    if not user.is_admin:
        await message.answer(text=texts["insufficient_privileges"])
        return
    game = await get_active_game(db_session)
    status = GameStatus.ACTIVE if game else None
    await message.answer(
        text=texts["admin_menu"], reply_markup=game_menu_kb(status=status)
    )


@router.message(Command("settings"))
async def settings_start(
    message: Message,
    state: FSMContext,
    user: User,
):
    await state.clear()
    user.IBAN = None
    user.bank = None
    user.name_surname = None
    first_field = ORDER[0]
    await state.set_state(getattr(SettingsForm, first_field))
    question = SETTINGS_QUESTIONS[first_field]
    await message.answer(question)


@router.message(Command("stats"))
async def stats_command(message: Message, user: User, db_session: AsyncSession):
    games_hosted = await games_hosting_count(user.id, db_session)
    games_played = await games_playing_count(user.id, db_session)
    mvp_count = await get_mvp_count(user.id, db_session)
    total_buy_in = await get_player_total_buy_in(user.id, db_session) or 0
    total_buy_out = await get_player_total_buy_out(user.id, db_session) or 0
    total_net = total_buy_out - total_buy_in
    if total_buy_in > 0:
        total_roi_value = (total_net / total_buy_in) * 100
        total_roi_str = f"{total_roi_value:.2f}%"
    else:
        total_roi_str = "0%" if total_buy_out == 0 else "∞%"

    active_game = await get_active_game(db_session)
    if active_game:
        try:
            record = await get_record(active_game.id, user.id, db_session)
            current_buy_in = record.buy_in or 0
        except NoResultFound:
            current_buy_in = 0
        await message.answer(
            text=texts["player_stats_ingame"].format(
                active_game.id,
                current_buy_in,
                games_played,
                games_hosted,
                mvp_count,
                total_buy_in,
                total_buy_out,
                total_roi_str,
            )
        )
    else:
        await message.answer(
            text=texts["player_stats_outgame"].format(
                games_played,
                games_hosted,
                mvp_count,
                total_buy_in,
                total_buy_out,
                total_roi_str,
            )
        )
