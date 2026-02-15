from aiogram.enums import ButtonStyle
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.internal.callbacks import CancelCbData, FinishGameCbData
from bot.internal.context import FinalGameAction
from bot.internal.lexicon import buttons


def finish_game_kb(game_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text=buttons["add_players_with_0"],
        callback_data=FinishGameCbData(
            action=FinalGameAction.ADD_PLAYERS_WITH_0, game_id=game_id
        ).pack(),
        style=ButtonStyle.PRIMARY,
    )
    builder.button(
        text=buttons["add_players_buyout"],
        callback_data=FinishGameCbData(
            action=FinalGameAction.ADD_PLAYERS_BUYOUT, game_id=game_id
        ).pack(),
        style=ButtonStyle.PRIMARY,
    )
    builder.button(
        text=buttons["finalize_game"],
        callback_data=FinishGameCbData(
            action=FinalGameAction.FINALIZE_GAME, game_id=game_id
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


def skip_photo_kb(game_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text=buttons["skip_photo"],
        callback_data=FinishGameCbData(
            action=FinalGameAction.SKIP_PHOTO_AND_FINALIZE, game_id=game_id
        ).pack(),
        style=ButtonStyle.DANGER,
    )
    return builder.as_markup()

