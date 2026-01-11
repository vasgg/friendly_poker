from enum import IntEnum, StrEnum, auto
from aiogram.filters.state import State, StatesGroup


class SettingsForm(StatesGroup):
    IBAN = State()
    bank = State()
    name_surname = State()


class Amount(IntEnum):
    FIVE_HUNDRED = 500
    ONE_THOUSAND = 1000
    FIFTEEN_HUNDRED = 1500
    TWO_THOUSAND = 2000
    TWO_AND_A_HALF_THOUSAND = 2500
    THREE_THOUSAND = 3000


class GameStatus(StrEnum):
    ACTIVE = auto()
    FINISHED = auto()
    ABORTED = auto()


class KeyboardMode(IntEnum):
    NEW_GAME = auto()
    ADD_PLAYERS = auto()
    PLAYERS_ADD_1000 = auto()
    PLAYERS_WITH_0 = auto()


class GameAction(IntEnum):
    ADD_PLAYERS = auto()
    START_GAME = auto()
    FINISH_GAME = auto()
    ABORT_GAME = auto()
    ADD_FUNDS = auto()
    ADD_PHOTO = auto()
    STATISTICS = auto()
    SELECT_RATIO = auto()
    SELECT_YEARLY_STATS = auto()


class RecordUpdateMode(IntEnum):
    UPDATE_BUY_IN = auto()
    UPDATE_BUY_OUT = auto()


class OperationType(IntEnum):
    MULTISELECT = auto()
    SINGLESELECT = auto()


class SinglePlayerActionType(IntEnum):
    CHOOSE_HOST = auto()
    ADD_FUNDS = auto()
    SET_BUY_OUT = auto()


class FinalGameAction(IntEnum):
    ADD_PLAYERS_WITH_0 = auto()
    ADD_PLAYERS_BUYOUT = auto()
    FINALIZE_GAME = auto()


class DebtAction(IntEnum):
    MARK_AS_PAID = auto()
    MARK_AS_UNPAID = auto()
    COMPLETE_DEBT = auto()


class DebtStatsView(IntEnum):
    I_OWE = auto()
    OWE_ME = auto()


class States(StatesGroup):
    ENTER_BUY_OUT = State()
    ADD_ADMIN = State()
    DELETE_ADMIN = State()
    ADD_PHOTO = State()
