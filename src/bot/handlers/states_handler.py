from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.controllers.record import update_record
from bot.controllers.user import get_user_from_db_by_tg_id
from bot.internal.dicts import texts
from bot.internal.enums import RecordUpdateMode, States

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
