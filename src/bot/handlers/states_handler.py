import html
import logging

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from aiogram.utils.chat_action import ChatActionSender
from sqlalchemy.ext.asyncio import AsyncSession

from bot.controllers.game import get_active_game
from bot.controllers.record import get_record, update_record
from bot.controllers.user import ask_next_question, get_user_from_db_by_tg_id
from bot.internal.context import RecordUpdateMode, SettingsForm, States
from bot.internal.keyboards import custom_funds_confirm_kb
from bot.internal.lexicon import ORDER, texts
from database.models import User

router = Router()
logger = logging.getLogger(__name__)


@router.message(States.ENTER_BUY_OUT)
async def enter_buy_out(
    message: Message,
    state: FSMContext,
    db_session: AsyncSession,
) -> None:
    data = await state.get_data()
    player_id = data["player_id"]
    game_id = data["game_id"]
    if message.text is None:
        await message.answer(text=texts["incorrect_buyout_value"])
        return
    try:
        value = int(message.text)
    except ValueError:
        await message.answer(text=texts["incorrect_buyout_value"])
        return
    if value < 0:
        await message.answer(text=texts["incorrect_buyout_value"])
        return
    player = await get_user_from_db_by_tg_id(player_id, db_session)
    player_name = html.escape(player.fullname) if player else "Unknown"
    await update_record(
        game_id=game_id,
        user_id=player_id,
        mode=RecordUpdateMode.UPDATE_BUY_OUT,
        value=value,
        db_session=db_session,
    )
    await state.set_state()
    await message.answer(
        text=texts["buy_out_updated"].format(game_id, player_name, value)
    )


@router.message(States.ENTER_CUSTOM_FUNDS)
async def enter_custom_funds(
    message: Message,
    state: FSMContext,
    db_session: AsyncSession,
) -> None:
    data = await state.get_data()
    player_id = data.get("custom_funds_player_id")
    game_id = data.get("custom_funds_game_id")
    if not player_id or not game_id:
        logger.warning("Custom funds entry missing context: user_id=%s", message.from_user.id)
        await message.answer(text=texts["custom_funds_not_ready"])
        return
    if message.text is None:
        await message.answer(text=texts["custom_funds_invalid"])
        return
    active_game = await get_active_game(db_session)
    if not active_game or active_game.id != game_id:
        await state.update_data(
            custom_funds_player_id=None,
            custom_funds_game_id=None,
            custom_funds_amount=None,
        )
        await state.set_state()
        logger.info(
            "Custom funds blocked: no active game for user_id=%s game_id=%s",
            message.from_user.id,
            game_id,
        )
        await message.answer(text=texts["no_active_game"])
        return
    record = await get_record(game_id, player_id, db_session)
    if record is None:
        await state.update_data(
            custom_funds_player_id=None,
            custom_funds_game_id=None,
            custom_funds_amount=None,
        )
        await state.set_state()
        logger.warning(
            "Custom funds blocked: player not in game. admin_id=%s player_id=%s game_id=%s",
            message.from_user.id,
            player_id,
            game_id,
        )
        await message.answer(text=texts["custom_funds_not_ready"])
        return
    try:
        value = int(message.text)
    except ValueError:
        logger.info(
            "Custom funds invalid amount: admin_id=%s value=%r",
            message.from_user.id,
            message.text,
        )
        await message.answer(text=texts["custom_funds_invalid"])
        return
    if value <= 0:
        logger.info(
            "Custom funds non-positive amount: admin_id=%s value=%s",
            message.from_user.id,
            value,
        )
        await message.answer(text=texts["custom_funds_invalid"])
        return
    player = await get_user_from_db_by_tg_id(player_id, db_session)
    if player is None:
        logger.warning(
            "Custom funds blocked: player missing. admin_id=%s player_id=%s game_id=%s",
            message.from_user.id,
            player_id,
            game_id,
        )
        await message.answer(text=texts["custom_funds_not_ready"])
        return
    await state.update_data(custom_funds_amount=value)
    logger.info(
        "Custom funds amount captured: admin_id=%s player_id=%s game_id=%s amount=%s",
        message.from_user.id,
        player_id,
        game_id,
        value,
    )
    await message.answer(
        text=texts["custom_funds_confirm"].format(value, html.escape(player.fullname)),
        reply_markup=custom_funds_confirm_kb(),
    )


@router.message(StateFilter(SettingsForm), F.text)
async def form_handler(
    message: Message,
    user: User,
    state: FSMContext,
    db_session: AsyncSession,
):
    current_state = await state.get_state()
    if current_state is None:
        await state.clear()
        return
    field = current_state.split(":")[-1]

    user_answer = message.text
    if not user_answer:
        return

    setattr(user, field, user_answer)
    db_session.add(user)
    await db_session.flush()

    async with ChatActionSender.typing(bot=message.bot, chat_id=message.chat.id):
        if all(getattr(user, f) for f in ORDER):
            await state.clear()
            await message.answer(text=texts["settings_updated"])
        else:
            next_field, next_question = await ask_next_question(user)
            await state.set_state(getattr(SettingsForm, next_field))
            await message.answer(next_question)
