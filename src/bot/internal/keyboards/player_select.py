from aiogram.enums import ButtonStyle
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.internal.callbacks import (
    CancelCbData,
    MultiselectFurtherCbData,
    PlayerCbData,
    SinglePlayerActionCbData,
)
from bot.internal.context import KeyboardMode, SinglePlayerActionType
from bot.internal.lexicon import buttons
from database.models import User


def choose_single_player_kb(
    mode: SinglePlayerActionType, players: list[User], game_id: int | None = None
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for player in players:
        builder.button(
            text=player.fullname,
            callback_data=SinglePlayerActionCbData(
                mode=mode, player_id=player.id, game_id=game_id
            ).pack(),
        )
    builder.button(
        text=buttons["cancel"],
        callback_data=CancelCbData().pack(),
        style=ButtonStyle.DANGER,
    )
    row_sizes = [2] * (len(players) // 2)
    if len(players) % 2:
        row_sizes.append(1)
    row_sizes.append(1)
    builder.adjust(*row_sizes)
    return builder.as_markup()


def users_multiselect_kb(
    players: list[User],
    mode: KeyboardMode,
    game_id: int,
    chosen: list[int] | None = None,
) -> InlineKeyboardMarkup:
    if not chosen:
        chosen = list()
    builder = InlineKeyboardBuilder()
    for player in players:
        if player.id in chosen:
            builder.button(
                text=player.fullname,
                callback_data=PlayerCbData(
                    player_id=player.id,
                    game_id=game_id,
                    name=player.fullname,
                    mode=mode,
                ).pack(),
                style=ButtonStyle.PRIMARY,
            )
        else:
            builder.button(
                text=player.fullname,
                callback_data=PlayerCbData(
                    player_id=player.id,
                    game_id=game_id,
                    name=player.fullname,
                    mode=mode,
                ).pack(),
            )
    builder.button(
        text=buttons["further_button"],
        callback_data=MultiselectFurtherCbData(mode=mode, game_id=game_id).pack(),
        style=ButtonStyle.SUCCESS,
    )
    builder.button(
        text=buttons["cancel"],
        callback_data=CancelCbData().pack(),
        style=ButtonStyle.DANGER,
    )
    row_sizes = [2] * (len(players) // 2)
    if len(players) % 2:
        row_sizes.append(1)
    row_sizes.extend([1, 1])
    builder.adjust(*row_sizes)
    return builder.as_markup()

