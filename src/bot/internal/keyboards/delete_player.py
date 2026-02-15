from aiogram.enums import ButtonStyle
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.internal.callbacks import (
    CancelCbData,
    DeletePlayerCancelCbData,
    DeletePlayerConfirmCbData,
    DeletePlayerPageCbData,
    DeletePlayerProceedCbData,
    DeletePlayerSelectCbData,
)
from bot.internal.lexicon import buttons
from database.models import User

MAX_BUTTON_TEXT_LENGTH = 64


def _format_player_label(player: User) -> str:
    games_played = player.games_played or 0
    suffix = f" ({games_played})"
    max_name_length = MAX_BUTTON_TEXT_LENGTH - len(suffix)
    name = player.fullname
    if max_name_length > 0 and len(name) > max_name_length:
        name = name[: max_name_length - 1] + "…"
    return f"{name}{suffix}"


def delete_player_list_kb(
    players: list[User],
    page: int,
    total_pages: int,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for player in players:
        builder.button(
            text=_format_player_label(player),
            callback_data=DeletePlayerSelectCbData(
                user_id=player.id,
                page=page,
            ).pack(),
        )
    if total_pages > 1:
        if page > 0:
            builder.button(
                text=buttons["page_prev"],
                callback_data=DeletePlayerPageCbData(page=page - 1).pack(),
            )
        if page < total_pages - 1:
            builder.button(
                text=buttons["page_next"],
                callback_data=DeletePlayerPageCbData(page=page + 1).pack(),
            )
    builder.adjust(2)
    return builder.as_markup()


def delete_player_summary_kb(
    user_id: int,
    page: int,
    has_debts: bool,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text=buttons["delete_anyway"] if has_debts else buttons["delete_player"],
        callback_data=DeletePlayerProceedCbData(
            user_id=user_id,
            page=page,
            force=has_debts,
        ).pack(),
        style=ButtonStyle.DANGER,
    )
    builder.button(
        text=buttons["back"],
        callback_data=DeletePlayerCancelCbData(page=page).pack(),
    )
    builder.button(
        text=buttons["cancel"],
        callback_data=CancelCbData().pack(),
    )
    builder.adjust(2, 1)
    return builder.as_markup()


def delete_player_confirm_kb(
    user_id: int,
    page: int,
    force: bool,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text=buttons["confirm_yes"],
        callback_data=DeletePlayerConfirmCbData(
            user_id=user_id,
            page=page,
            force=force,
        ).pack(),
        style=ButtonStyle.DANGER,
    )
    builder.button(
        text=buttons["back"],
        callback_data=DeletePlayerCancelCbData(page=page).pack(),
    )
    builder.button(
        text=buttons["cancel"],
        callback_data=CancelCbData().pack(),
    )
    builder.adjust(2, 1)
    return builder.as_markup()
