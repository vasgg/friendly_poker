from aiogram.filters.callback_data import CallbackData

from bot.internal.context import (
    DebtAction,
    DebtStatsView,
    FinalGameAction,
    GameAction,
    KeyboardMode,
    OperationType,
    SinglePlayerActionType,
)


class PlayerCbData(CallbackData, prefix="p"):
    player_id: int
    game_id: int
    name: str
    mode: KeyboardMode


class SinglePlayerActionCbData(CallbackData, prefix="single_p_action"):
    mode: SinglePlayerActionType
    player_id: int
    game_id: int | None = None


class GameMenuCbData(CallbackData, prefix="game_menu"):
    action: GameAction


class MultiselectFurtherCbData(CallbackData, prefix="mltslct_further"):
    mode: KeyboardMode
    game_id: int


class AddFundsOperationType(CallbackData, prefix="add_funds_type"):
    type: OperationType
    game_id: int


class CancelCbData(CallbackData, prefix="mltslct_cancel"):
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


class GameModeCbData(CallbackData, prefix="game_mode"):
    ratio: int


class NextGameRatioConfirmCbData(CallbackData, prefix="next_ratio_confirm"):
    ratio: int
    confirm: bool


class NextGameYearlyStatsConfirmCbData(CallbackData, prefix="next_yearly_confirm"):
    confirm: bool


class DebtStatsCbData(CallbackData, prefix="debt_stats"):
    view: DebtStatsView


class CustomFundsConfirmCbData(CallbackData, prefix="custom_funds"):
    confirm: bool


class DeletePlayerSelectCbData(CallbackData, prefix="del_player"):
    user_id: int
    page: int


class DeletePlayerPageCbData(CallbackData, prefix="del_player_page"):
    page: int


class DeletePlayerProceedCbData(CallbackData, prefix="del_player_proceed"):
    user_id: int
    page: int
    force: bool


class DeletePlayerConfirmCbData(CallbackData, prefix="del_player_confirm"):
    user_id: int
    page: int
    force: bool


class DeletePlayerCancelCbData(CallbackData, prefix="del_player_cancel"):
    page: int
