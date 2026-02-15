from aiogram.enums import ButtonStyle
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.internal.callbacks import AbortDialogCbData, CancelCbData, GameMenuCbData
from bot.internal.context import GameAction, GameStatus
from bot.internal.lexicon import buttons


def confirmation_dialog_kb(game_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text=buttons["abort_game_button_yes"],
        callback_data=AbortDialogCbData(game_id=game_id).pack(),
        style=ButtonStyle.DANGER,
    )
    builder.button(
        text=buttons["confirm_no"],
        callback_data=CancelCbData().pack(),
    )
    builder.adjust(2)
    return builder.as_markup()


def game_menu_kb(status: GameStatus | None, is_admin: bool = True) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    match status:
        case GameStatus.ACTIVE:
            builder.button(
                text=buttons["menu_add_players"],
                callback_data=GameMenuCbData(action=GameAction.ADD_PLAYERS).pack(),
            )
            builder.button(
                text=buttons["menu_add_funds"],
                callback_data=GameMenuCbData(action=GameAction.ADD_FUNDS).pack(),
                style=ButtonStyle.SUCCESS,
            )
            if is_admin:
                builder.button(
                    text=buttons["menu_statistics"],
                    callback_data=GameMenuCbData(action=GameAction.STATISTICS).pack(),
                )
            builder.button(
                text=buttons["menu_finish_game"],
                callback_data=GameMenuCbData(action=GameAction.FINISH_GAME).pack(),
                style=ButtonStyle.PRIMARY,
            )
            builder.button(
                text=buttons["menu_abort_game"],
                callback_data=GameMenuCbData(action=GameAction.ABORT_GAME).pack(),
                style=ButtonStyle.DANGER,
            )
            builder.button(
                text=buttons["menu_new_year"],
                callback_data=GameMenuCbData(action=GameAction.NEXT_GAME_SETTINGS).pack(),
            )
        case _:
            builder.button(
                text=buttons["menu_start_game"],
                callback_data=GameMenuCbData(action=GameAction.START_GAME).pack(),
                style=ButtonStyle.PRIMARY,
            )
            if is_admin:
                builder.button(
                    text=buttons["menu_statistics"],
                    callback_data=GameMenuCbData(action=GameAction.STATISTICS).pack(),
                )
            builder.button(
                text=buttons["menu_new_year"],
                callback_data=GameMenuCbData(action=GameAction.NEXT_GAME_SETTINGS).pack(),
            )
    builder.adjust(1)
    return builder.as_markup()


def next_game_menu_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text=buttons["menu_select_ratio"],
        callback_data=GameMenuCbData(action=GameAction.SELECT_RATIO).pack(),
    )
    builder.button(
        text=buttons["menu_select_yearly_stats"],
        callback_data=GameMenuCbData(action=GameAction.SELECT_YEARLY_STATS).pack(),
    )
    builder.button(
        text=buttons["menu_delete_player"],
        callback_data=GameMenuCbData(action=GameAction.DELETE_PLAYER).pack(),
        style=ButtonStyle.DANGER,
    )
    builder.button(
        text=buttons["back"],
        callback_data=CancelCbData().pack(),
    )
    builder.adjust(1)
    return builder.as_markup()

