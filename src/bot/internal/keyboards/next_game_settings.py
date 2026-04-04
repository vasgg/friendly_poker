from aiogram.enums import ButtonStyle
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.internal.callbacks import (
    CancelCbData,
    GameModeCbData,
    NextGameRatioConfirmCbData,
    NextGameYearlyStatsConfirmCbData,
)
from bot.internal.lexicon import buttons


def ratio_confirm_kb(ratio: int, version: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text=buttons["confirm_yes"],
        callback_data=NextGameRatioConfirmCbData(
            ratio=ratio,
            confirm=True,
            version=version,
        ).pack(),
        style=ButtonStyle.SUCCESS,
    )
    builder.button(
        text=buttons["confirm_no"],
        callback_data=NextGameRatioConfirmCbData(
            ratio=ratio,
            confirm=False,
            version=version,
        ).pack(),
        style=ButtonStyle.DANGER,
    )
    builder.adjust(2)
    return builder.as_markup()


def yearly_stats_confirm_kb(version: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text=buttons["confirm_yes"],
        callback_data=NextGameYearlyStatsConfirmCbData(
            confirm=True,
            version=version,
        ).pack(),
        style=ButtonStyle.SUCCESS,
    )
    builder.button(
        text=buttons["confirm_no"],
        callback_data=NextGameYearlyStatsConfirmCbData(
            confirm=False,
            version=version,
        ).pack(),
        style=ButtonStyle.DANGER,
    )
    builder.adjust(2)
    return builder.as_markup()


def select_ratio_kb(version: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text=buttons["ratio_option"].format(1),
        callback_data=GameModeCbData(ratio=1, version=version).pack(),
    )
    builder.button(
        text=buttons["ratio_option"].format(2),
        callback_data=GameModeCbData(ratio=2, version=version).pack(),
    )
    builder.button(
        text=buttons["ratio_option"].format(3),
        callback_data=GameModeCbData(ratio=3, version=version).pack(),
    )
    builder.button(
        text=buttons["ratio_option"].format(4),
        callback_data=GameModeCbData(ratio=4, version=version).pack(),
    )
    builder.button(
        text=buttons["cancel"],
        callback_data=CancelCbData().pack(),
        style=ButtonStyle.DANGER,
    )
    builder.adjust(2, 2, 1)
    return builder.as_markup()
