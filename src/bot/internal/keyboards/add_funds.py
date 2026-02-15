from aiogram.enums import ButtonStyle
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.internal.callbacks import AddFundsOperationType, CancelCbData, CustomFundsConfirmCbData
from bot.internal.context import OperationType
from bot.internal.lexicon import buttons


def mode_selector_kb(game_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text=buttons["multi_selector"],
        callback_data=AddFundsOperationType(
            type=OperationType.MULTISELECT, game_id=game_id
        ).pack(),
        style=ButtonStyle.SUCCESS,
    )
    builder.button(
        text=buttons["single_selector"],
        callback_data=AddFundsOperationType(
            type=OperationType.SINGLESELECT, game_id=game_id
        ).pack(),
        style=ButtonStyle.PRIMARY,
    )
    builder.button(
        text=buttons["cancel"],
        callback_data=CancelCbData().pack(),
        style=ButtonStyle.DANGER,
    )
    builder.adjust(1)
    return builder.as_markup()


def custom_funds_confirm_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text=buttons["confirm_yes"],
        callback_data=CustomFundsConfirmCbData(confirm=True).pack(),
        style=ButtonStyle.SUCCESS,
    )
    builder.button(
        text=buttons["confirm_no"],
        callback_data=CustomFundsConfirmCbData(confirm=False).pack(),
        style=ButtonStyle.DANGER,
    )
    builder.button(
        text=buttons["cancel"],
        callback_data=CancelCbData().pack(),
    )
    builder.adjust(2, 1)
    return builder.as_markup()

