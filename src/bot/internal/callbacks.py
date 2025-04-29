from aiogram.filters.callback_data import CallbackData

from bot.internal.context import (
    DebtAction, FinalGameAction,
    GameAction,
    KeyboardMode,
    OperationType,
    SinglePlayerActionType,
)


class PlayerCbData(CallbackData, prefix="player"):
    player_id: int
    game_id: int
    name: str
    mode: KeyboardMode


class SinglePlayerActionCbData(CallbackData, prefix="single_player_action"):
    mode: SinglePlayerActionType
    player_id: int
    game_id: int | None = None


class GameMenuCbData(CallbackData, prefix="game_menu"):
    action: GameAction


class MultiselectFurtherCbData(CallbackData, prefix="multiselect_further"):
    mode: KeyboardMode
    game_id: int


class AddFundsOperationType(CallbackData, prefix="add_funds_type"):
    type: OperationType
    game_id: int


class CancelCbData(CallbackData, prefix="multiselect_cancel"):
    pass


class AbortDialogCbData(CallbackData, prefix="abort_game"):
    game_id: int


class FinishGameCbData(CallbackData, prefix="finish_game"):
    action: FinalGameAction
    game_id: int


class DebtActionCbData(CallbackData, prefix="debt_action"):
    action: DebtAction
    debt_id: int
    chat_id: int
