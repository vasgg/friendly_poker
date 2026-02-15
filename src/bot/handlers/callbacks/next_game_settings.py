from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from bot.handlers.callbacks.common import _edit_or_answer
from bot.internal.callbacks import (
    GameModeCbData,
    NextGameRatioConfirmCbData,
    NextGameYearlyStatsConfirmCbData,
)
from bot.internal.keyboards import next_game_menu_kb, ratio_confirm_kb, select_ratio_kb
from bot.internal.lexicon import texts
from database.models import User

router = Router()


@router.callback_query(GameModeCbData.filter())
async def game_mode_handler(
    callback: CallbackQuery,
    callback_data: GameModeCbData,
    user: User,
) -> None:
    await callback.answer()
    if not user.is_admin:
        await callback.message.answer(text=texts["insufficient_privileges"])
        return
    await _edit_or_answer(
        callback.message,
        text=texts["ratio_confirm"].format(callback_data.ratio),
        reply_markup=ratio_confirm_kb(callback_data.ratio),
    )


@router.callback_query(NextGameRatioConfirmCbData.filter())
async def next_game_ratio_confirm_handler(
    callback: CallbackQuery,
    callback_data: NextGameRatioConfirmCbData,
    user: User,
    state: FSMContext,
) -> None:
    await callback.answer()
    if not user.is_admin:
        await callback.message.answer(text=texts["insufficient_privileges"])
        return
    if callback_data.confirm:
        await state.update_data(next_game_ratio=callback_data.ratio)
        await _edit_or_answer(
            callback.message,
            text=texts["ratio_set"].format(callback_data.ratio),
            reply_markup=next_game_menu_kb(),
        )
        return
    await _edit_or_answer(
        callback.message,
        text=texts["select_mode_prompt"],
        reply_markup=select_ratio_kb(),
    )


@router.callback_query(NextGameYearlyStatsConfirmCbData.filter())
async def next_game_yearly_stats_confirm_handler(
    callback: CallbackQuery,
    callback_data: NextGameYearlyStatsConfirmCbData,
    user: User,
    state: FSMContext,
) -> None:
    await callback.answer()
    if not user.is_admin:
        await callback.message.answer(text=texts["insufficient_privileges"])
        return
    if callback_data.confirm:
        await state.update_data(next_game_yearly_stats=True)
        text = texts["yearly_stats_set"]
    else:
        text = texts["admin_next_game_menu"]
    await _edit_or_answer(
        callback.message,
        text=text,
        reply_markup=next_game_menu_kb(),
    )
