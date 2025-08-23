from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.internal.callbacks import (
    AbortDialogCbData,
    AddFundsOperationType,
    DebtActionCbData,
    FinishGameCbData,
    GameMenuCbData,
    SinglePlayerActionCbData,
    CancelCbData,
    MultiselectFurtherCbData,
    PlayerCbData,
)
from bot.internal.lexicon import buttons
from bot.internal.context import (
    DebtAction,
    FinalGameAction,
    GameAction,
    GameStatus,
    KeyboardMode,
    OperationType,
    SinglePlayerActionType,
)
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
    builder.button(text=buttons["cancel_button"], callback_data=CancelCbData().pack())
    builder.adjust(*([2] * (len(players) // 2)) + [1])
    return builder.as_markup()


def mode_selector_kb(game_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text=buttons["multi_selector"],
        callback_data=AddFundsOperationType(
            type=OperationType.MULTISELECT, game_id=game_id
        ).pack(),
    )
    builder.button(
        text=buttons["single_selector"],
        callback_data=AddFundsOperationType(
            type=OperationType.SINGLESELECT, game_id=game_id
        ).pack(),
    )
    builder.adjust(1)
    return builder.as_markup()


def confirmation_dialog_kb(game_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text=buttons["abort_game_button_yes"],
        callback_data=AbortDialogCbData(game_id=game_id).pack(),
    )
    builder.button(text=buttons["cancel_button"], callback_data=CancelCbData().pack())
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
        builder.button(
            text=("✅ " if player.id in chosen else "") + player.fullname,
            callback_data=PlayerCbData(
                player_id=player.id,
                game_id=game_id,
                name=player.fullname,
                mode=mode,
            ).pack(),
        )
    builder.button(
        text=buttons["futher_button"],
        callback_data=MultiselectFurtherCbData(mode=mode, game_id=game_id).pack(),
    )
    builder.button(text=buttons["cancel_button"], callback_data=CancelCbData().pack())
    builder.adjust(*([2] * (len(players) // 2)) + [1, 1])
    return builder.as_markup()


def game_menu_kb(status: GameStatus | None) -> InlineKeyboardMarkup:
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
            )
            builder.button(
                text=buttons["menu_add_photo"],
                callback_data=GameMenuCbData(action=GameAction.ADD_PHOTO).pack(),
            )
            builder.button(
                text=buttons["menu_finish_game"],
                callback_data=GameMenuCbData(action=GameAction.FINISH_GAME).pack(),
            )
            builder.button(
                text=buttons["menu_abort_game"],
                callback_data=GameMenuCbData(action=GameAction.ABORT_GAME).pack(),
            )
        case _:
            builder.button(
                text=buttons["menu_start_game"],
                callback_data=GameMenuCbData(action=GameAction.START_GAME).pack(),
            )
            builder.button(
                text=buttons["menu_statistics"],
                callback_data=GameMenuCbData(action=GameAction.STATISTICS).pack(),
            )
    builder.adjust(2)
    return builder.as_markup()


def finish_game_kb(game_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text=buttons["add_players_with_0"],
        callback_data=FinishGameCbData(
            action=FinalGameAction.ADD_PLAYERS_WITH_0, game_id=game_id
        ).pack(),
    )
    builder.button(
        text=buttons["add_players_buyout"],
        callback_data=FinishGameCbData(
            action=FinalGameAction.ADD_PLAYERS_BUYOUT, game_id=game_id
        ).pack(),
    )
    builder.button(
        text=buttons["finalize_game"],
        callback_data=FinishGameCbData(
            action=FinalGameAction.FINALIZE_GAME, game_id=game_id
        ).pack(),
    )
    builder.adjust(1)
    return builder.as_markup()


async def get_paid_button(debt_id, chat_id):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="DEBT PAID",
                    callback_data=DebtActionCbData(
                        action=DebtAction.MARK_AS_PAID,
                        debt_id=debt_id,
                        chat_id=chat_id,
                    ).pack(),
                )
            ],
        ]
    )


async def get_paid_button_confirmation(debt_id, chat_id):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="confirm payment",
                    callback_data=DebtActionCbData(
                        action=DebtAction.COMPLETE_DEBT,
                        debt_id=debt_id,
                        chat_id=chat_id,
                    ).pack(),
                )
            ],
            # [
            #     InlineKeyboardButton(
            #         text="NOPE",
            #         callback_data=DebtActionCbData(
            #             action=DebtAction.MARK_AS_UNPAID,
            #             debt_id=debt_id,
            #             chat_id=chat_id,
            #         ).pack(),
            #     )
            # ],
        ],
    )
