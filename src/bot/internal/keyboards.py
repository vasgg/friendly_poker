from aiogram.enums import ButtonStyle
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.internal.callbacks import (
    AbortDialogCbData,
    AddFundsOperationType,
    CancelCbData,
    CustomFundsConfirmCbData,
    DebtActionCbData,
    DebtStatsCbData,
    DeletePlayerCancelCbData,
    DeletePlayerConfirmCbData,
    DeletePlayerPageCbData,
    DeletePlayerProceedCbData,
    DeletePlayerSelectCbData,
    FinishGameCbData,
    GameMenuCbData,
    GameModeCbData,
    MultiselectFurtherCbData,
    PlayerCbData,
    SinglePlayerActionCbData,
)
from bot.internal.context import (
    DebtAction,
    DebtStatsView,
    FinalGameAction,
    GameAction,
    GameStatus,
    KeyboardMode,
    OperationType,
    SinglePlayerActionType,
)
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


def delete_player_list_kb(
    players: list[User],
    page: int,
    total_pages: int,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for player in players:
        builder.button(
            text=player.fullname,
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


def select_ratio_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="x1", callback_data=GameModeCbData(ratio=1).pack())
    builder.button(text="x2", callback_data=GameModeCbData(ratio=2).pack())
    builder.button(text="x3", callback_data=GameModeCbData(ratio=3).pack())
    builder.button(text="x4", callback_data=GameModeCbData(ratio=4).pack())
    builder.button(
        text=buttons["cancel"],
        callback_data=CancelCbData().pack(),
        style=ButtonStyle.DANGER,
    )
    builder.adjust(2, 2, 1)
    return builder.as_markup()


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
                    style=ButtonStyle.SUCCESS,
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
                    style=ButtonStyle.SUCCESS,
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


def debt_details_i_owe_kb(debts, user_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for debt in debts:
        builder.button(
            text=buttons["debt_detail_paid"].format(debt.game_id, debt.creditor.fullname),
            callback_data=DebtActionCbData(
                action=DebtAction.MARK_AS_PAID,
                debt_id=debt.id,
                chat_id=user_id,
            ).pack(),
            style=ButtonStyle.SUCCESS,
        )
    builder.adjust(1)
    return builder.as_markup()


def debt_details_owe_me_kb(debts, user_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for debt in debts:
        builder.button(
            text=buttons["debt_detail_remind"].format(debt.game_id, debt.debtor.fullname),
            callback_data=DebtActionCbData(
                action=DebtAction.REMIND_DEBTOR,
                debt_id=debt.id,
                chat_id=user_id,
            ).pack(),
            style=ButtonStyle.PRIMARY,
        )
    builder.adjust(1)
    return builder.as_markup()


def debt_stats_kb(has_debts_i_owe: bool, has_debts_owe_me: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if has_debts_i_owe:
        builder.button(
            text=buttons["debt_stats_i_owe"],
            callback_data=DebtStatsCbData(view=DebtStatsView.I_OWE).pack(),
            style=ButtonStyle.DANGER,
        )
    if has_debts_owe_me:
        builder.button(
            text=buttons["debt_stats_owe_me"],
            callback_data=DebtStatsCbData(view=DebtStatsView.OWE_ME).pack(),
            style=ButtonStyle.SUCCESS,
        )
    builder.adjust(2)
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
