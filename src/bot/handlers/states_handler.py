from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from aiogram.utils.chat_action import ChatActionSender
from sqlalchemy.ext.asyncio import AsyncSession

from bot.controllers.record import update_record
from bot.controllers.user import ask_next_question, get_user_from_db_by_tg_id
from bot.internal.lexicon import ORDER, texts
from bot.internal.context import RecordUpdateMode, SettingsForm, States
from database.models import User

router = Router()


@router.message(States.ENTER_BUY_OUT)
async def enter_buy_out(
    message: Message,
    state: FSMContext,
    db_session: AsyncSession,
) -> None:
    data = await state.get_data()
    player_id = data["player_id"]
    game_id = data["game_id"]
    try:
        value = int(message.text)
    except ValueError:
        await message.answer(text=texts["incorrect_buyout_value"])
        return
    if value < 0:
        await message.answer(text=texts["incorrect_buyout_value"])
        return
    player = await get_user_from_db_by_tg_id(player_id, db_session)
    await update_record(
        game_id=game_id,
        user_id=player_id,
        mode=RecordUpdateMode.UPDATE_BUY_OUT,
        value=value,
        db_session=db_session,
    )
    await state.set_state()
    await message.answer(
        text=texts["buy_out_updated"].format(game_id, player.fullname, value)
    )


@router.message(StateFilter(SettingsForm), F.text)
async def form_handler(
    message: Message,
    user: User,
    state: FSMContext,
    db_session: AsyncSession,
):
    current_state = await state.get_state()
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
