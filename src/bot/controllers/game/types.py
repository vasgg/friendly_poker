from dataclasses import dataclass


@dataclass(slots=True)
class YearlySummary:
    total_games: int
    total_players: int
    biggest_pot: int
    biggest_pot_game_id: int | None
    total_buy_in: int
    total_duration_seconds: int
    best_single_game_roi: float | None
    best_single_game_roi_names: list[str]
    top_mvp_names: list[str]
    top_mvp_count: int
    top_host_names: list[str]
    top_host_games: int


@dataclass(slots=True)
class YearlyPlayerStats:
    user_id: int
    fullname: str
    games_played: int
    total_buy_in: int
    total_buy_out: int
    net: int
    roi: float | None

