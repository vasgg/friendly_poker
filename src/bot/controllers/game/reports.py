import html

from sqlalchemy.ext.asyncio import AsyncSession

from bot.controllers.game.crud import get_game_by_id
from bot.controllers.game.types import YearlyPlayerStats, YearlySummary
from bot.internal.lexicon import texts


def format_duration(seconds: int) -> str:
    hours, remainder = divmod(seconds, 3600)
    minutes, _ = divmod(remainder, 60)
    return f"{hours}h {minutes}m" if hours else f"{minutes}m"


def format_duration_with_days(seconds: int) -> str:
    minutes, _ = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours or days:
        parts.append(f"{hours}h")
    parts.append(f"{minutes}m")
    return " ".join(parts)


def _generate_stats_report(
    title: str, summary: YearlySummary, players: list[YearlyPlayerStats]
) -> str:
    lines = [
        f"<b>{title}</b>",
        f"Total games: <b>{summary.total_games}</b>",
        f"Total players: <b>{summary.total_players}</b>",
        f"Biggest pot: <b>{summary.biggest_pot}</b> (game {summary.biggest_pot_game_id})",
        f"Total pot: <b>{summary.total_buy_in}</b>",
        f"Total duration: <b>{format_duration_with_days(summary.total_duration_seconds)}</b>",
    ]

    if (
        players
        or summary.best_single_game_roi_names
        or summary.top_mvp_names
        or summary.top_host_names
    ):
        lines.append("")
        lines.append("<b>Records</b>")
    if players:
        most_games_value = max(p.games_played for p in players)
        most_games_names = sorted(
            p.fullname for p in players if p.games_played == most_games_value
        )
        best_profit_value = max(p.net for p in players)
        best_profit_names = sorted(p.fullname for p in players if p.net == best_profit_value)
        most_buy_in_value = max(p.total_buy_in for p in players)
        most_buy_in_names = sorted(
            p.fullname for p in players if p.total_buy_in == most_buy_in_value
        )
        roi_candidates = [p for p in players if p.roi is not None]
        if roi_candidates:
            best_total_roi_value = max(p.roi for p in roi_candidates)
            best_total_roi_names = sorted(
                p.fullname for p in roi_candidates if p.roi == best_total_roi_value
            )
        else:
            best_total_roi_value = None
            best_total_roi_names = []

        most_games_label = html.escape(", ".join(most_games_names))
        best_profit_label = html.escape(", ".join(best_profit_names))
        most_buy_in_label = html.escape(", ".join(most_buy_in_names))
        best_total_roi_label = html.escape(", ".join(best_total_roi_names))

        lines.append(f"Most games: <b>{most_games_label}</b> ({most_games_value})")
        lines.append(f"Best profit: <b>{best_profit_label}</b> ({best_profit_value})")
        lines.append(f"Most buy-in: <b>{most_buy_in_label}</b> ({most_buy_in_value})")
        if summary.best_single_game_roi_names:
            best_single_roi_label = html.escape(", ".join(summary.best_single_game_roi_names))
            lines.append(
                f"Best ROI (single game): <b>{best_single_roi_label}</b> "
                f"({summary.best_single_game_roi:.2f}%)"
            )
        if best_total_roi_names:
            lines.append(
                f"Best total ROI: <b>{best_total_roi_label}</b> "
                f"({best_total_roi_value:.2f}%)"
            )
    if summary.top_mvp_names:
        top_mvp_label = html.escape(", ".join(sorted(summary.top_mvp_names)))
        lines.append(f"Top MVP: <b>{top_mvp_label}</b> — {summary.top_mvp_count} awards")
    if summary.top_host_names:
        top_host_label = html.escape(", ".join(sorted(summary.top_host_names)))
        host_share = (
            (summary.top_host_games / summary.total_games) * 100 if summary.total_games else 0
        )
        lines.append(
            f"Top host: <b>{top_host_label}</b> ({summary.top_host_games} games, {host_share:.1f}%)"
        )

    return "\n".join(lines)


def generate_yearly_stats_report(
    year: int, summary: YearlySummary, players: list[YearlyPlayerStats]
) -> str:
    return _generate_stats_report(f"Year {year} summary", summary, players)


def generate_all_time_stats_report(
    summary: YearlySummary, players: list[YearlyPlayerStats]
) -> str:
    return _generate_stats_report("All-time summary", summary, players)


async def get_group_game_report(
    game_id: int, name: str, roi: float, db_session: AsyncSession
) -> str:
    game = await get_game_by_id(game_id, db_session)
    if game is None:
        return texts["game_not_found"].format(game_id)
    duration = format_duration(game.duration or 0)
    safe_name = html.escape(name)
    return texts["global_game_report"].format(
        game_id,
        duration,
        game.total_pot or 0,
        safe_name,
        roi,
    )

