from dataclasses import dataclass
from datetime import datetime
import html
import logging

from sqlalchemy import select, update, func, extract
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from bot.config import settings
from bot.internal.lexicon import texts
from bot.internal.context import GameStatus
from database.models import Game, Record, User

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class YearlySummary:
    total_games: int
    total_players: int
    total_buy_in: int
    total_duration_seconds: int
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


async def get_active_game(db_session: AsyncSession) -> Game | None:
    query = (
        select(Game)
        .where(Game.status == GameStatus.ACTIVE)
        .options(joinedload(Game.records))
    )
    result = await db_session.execute(query)
    games = result.unique().scalars().all()
    if not games:
        return None

    if len(games) > 1:
        logger.error(f"Found {len(games)} active games! Returning the most recent one.")
        games = sorted(games, key=lambda g: g.id, reverse=True)

    game = games[0]
    if game:
        logger.info(
            f"Active game: {game.id=}, {game.host_id=}, players: {len(game.records)}"
        )
    return game


async def get_game_by_id(game_id: int, db_session: AsyncSession) -> Game:
    query = select(Game).where(Game.id == game_id)
    result = await db_session.execute(query)
    return result.unique().scalar_one()


async def create_game(
    admin_id: int, host_id: int, db_session: AsyncSession, ratio: int = 1
) -> Game:
    new_game = Game(
        admin_id=admin_id,
        host_id=host_id,
        ratio=ratio,
    )
    db_session.add(new_game)
    await db_session.flush()
    logger.info(f"New game created: {new_game.id=}, {new_game.host_id=}")
    return new_game


async def abort_game(game_id: int, db_session: AsyncSession) -> None:
    query = update(Game).where(Game.id == game_id).values(status=GameStatus.ABORTED)
    await db_session.execute(query)


async def commit_game_results_to_db(
    game_id: int, total_pot: int, mvp_id: int, db_session: AsyncSession
) -> None:
    now = datetime.now(settings.bot.TIMEZONE)
    game: Game = await get_game_by_id(game_id, db_session)
    start_time: datetime = game.created_at
    if start_time.tzinfo is None:
        start_time = start_time.replace(tzinfo=settings.bot.TIMEZONE)
    delta = now - start_time

    duration_in_seconds = int(delta.total_seconds())
    close_game = (
        update(Game)
        .where(Game.id == game_id)
        .values(
            status=GameStatus.FINISHED,
            duration=duration_in_seconds,
            total_pot=total_pot,
            mvp_id=mvp_id,
        )
    )
    await db_session.execute(close_game)


def format_player_line(name: str, amount: int) -> str:
    width = 50
    max_name_len = 20
    max_amount_len = 8
    dots = "."

    formatted_name = (
        (name[: max_name_len - 1] + "…") if len(name) > max_name_len else name
    )

    formatted_amount = f"{amount:>{max_amount_len}}"

    dots_count = width - len(formatted_name) - len(formatted_amount) - 4
    dots_str = dots * max(dots_count, 1)

    return f"│ {formatted_name} {dots_str} {formatted_amount} │"


def generate_poker_report(players: list) -> str:
    width = 50
    top_border = "┌" + "─" * (width - 2) + "┐"
    bottom_border = "└" + "─" * (width - 2) + "┘"
    separator = "├" + "─" * (width - 2) + "┤"
    header = f"│ {'Игроки':<{width - 2}} │"

    player_lines = [format_player_line(name, amount) for name, amount in players]

    return "\n".join([top_border, header, separator] + player_lines + [bottom_border])


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


async def get_yearly_stats(
    year: int, db_session: AsyncSession
) -> tuple[YearlySummary, list[YearlyPlayerStats]]:
    summary_query = (
        select(
            func.count(func.distinct(Game.id)).label("games_count"),
            func.count(func.distinct(Record.user_id)).label("players_count"),
            func.coalesce(func.sum(Record.buy_in), 0).label("total_buy_in"),
        )
        .join(Record, Record.game_id == Game.id)
        .where(Game.status == GameStatus.FINISHED)
        .where(extract("year", Game.created_at) == year)
    )
    summary_result = await db_session.execute(summary_query)
    total_games, total_players, total_buy_in = summary_result.one()

    duration_query = (
        select(func.coalesce(func.sum(Game.duration), 0))
        .where(Game.status == GameStatus.FINISHED)
        .where(extract("year", Game.created_at) == year)
    )
    duration_result = await db_session.execute(duration_query)
    (total_duration_seconds,) = duration_result.one()

    players_query = (
        select(
            User.id,
            User.fullname,
            func.count(Record.id).label("games_played"),
            func.coalesce(func.sum(Record.buy_in), 0).label("total_buy_in"),
            func.coalesce(func.sum(Record.buy_out), 0).label("total_buy_out"),
        )
        .join(Record, Record.user_id == User.id)
        .join(Game, Game.id == Record.game_id)
        .where(Game.status == GameStatus.FINISHED)
        .where(extract("year", Game.created_at) == year)
        .group_by(User.id, User.fullname)
        .order_by(User.fullname)
    )
    players_result = await db_session.execute(players_query)
    players_rows = players_result.all()
    players_stats: list[YearlyPlayerStats] = []
    for user_id, fullname, games_played, buy_in, buy_out in players_rows:
        net = (buy_out or 0) - (buy_in or 0)
        roi = round((net / buy_in) * 100, 2) if buy_in else None
        players_stats.append(
            YearlyPlayerStats(
                user_id=user_id,
                fullname=fullname,
                games_played=games_played or 0,
                total_buy_in=buy_in or 0,
                total_buy_out=buy_out or 0,
                net=net,
                roi=roi,
            )
        )

    host_query = (
        select(
            User.fullname,
            func.count(Game.id).label("games_hosted"),
        )
        .join(Game, Game.host_id == User.id)
        .where(Game.status == GameStatus.FINISHED)
        .where(extract("year", Game.created_at) == year)
        .group_by(User.id, User.fullname)
        .order_by(func.count(Game.id).desc())
    )
    host_result = await db_session.execute(host_query)
    host_rows = host_result.all()
    if host_rows:
        top_host_games = max(row[1] for row in host_rows)
        top_host_names = [row[0] for row in host_rows if row[1] == top_host_games]
    else:
        top_host_names, top_host_games = [], 0

    mvp_query = (
        select(
            User.fullname,
            func.count(Game.id).label("mvp_count"),
        )
        .join(Game, Game.mvp_id == User.id)
        .where(Game.status == GameStatus.FINISHED)
        .where(Game.mvp_id.isnot(None))
        .where(extract("year", Game.created_at) == year)
        .group_by(User.id, User.fullname)
        .order_by(func.count(Game.id).desc())
    )
    mvp_result = await db_session.execute(mvp_query)
    mvp_rows = mvp_result.all()
    if mvp_rows:
        top_mvp_count = max(row[1] for row in mvp_rows)
        top_mvp_names = [row[0] for row in mvp_rows if row[1] == top_mvp_count]
    else:
        top_mvp_names, top_mvp_count = [], 0

    summary = YearlySummary(
        total_games=total_games or 0,
        total_players=total_players or 0,
        total_buy_in=total_buy_in or 0,
        total_duration_seconds=total_duration_seconds or 0,
        top_mvp_names=top_mvp_names,
        top_mvp_count=top_mvp_count or 0,
        top_host_names=top_host_names,
        top_host_games=top_host_games or 0,
    )

    return summary, players_stats


def generate_yearly_stats_report(
    year: int, summary: YearlySummary, players: list[YearlyPlayerStats]
) -> str:
    lines = [
        f"<b>Year {year} summary</b>",
        f"Total games: <b>{summary.total_games}</b>",
        f"Total players: <b>{summary.total_players}</b>",
        f"Total buy-in: <b>{summary.total_buy_in}</b>",
        f"Total duration: <b>{format_duration_with_days(summary.total_duration_seconds)}</b>",
    ]

    if players or summary.top_mvp_names or summary.top_host_names:
        lines.append("")
        lines.append("<b>Records</b>")
    if players:
        most_games_value = max(p.games_played for p in players)
        most_games_names = sorted(
            p.fullname for p in players if p.games_played == most_games_value
        )
        best_profit_value = max(p.net for p in players)
        best_profit_names = sorted(
            p.fullname for p in players if p.net == best_profit_value
        )
        most_buy_in_value = max(p.total_buy_in for p in players)
        most_buy_in_names = sorted(
            p.fullname for p in players if p.total_buy_in == most_buy_in_value
        )
        roi_candidates = [p for p in players if p.roi is not None]
        if roi_candidates:
            best_roi_value = max(p.roi for p in roi_candidates)
            best_roi_names = sorted(
                p.fullname for p in roi_candidates if p.roi == best_roi_value
            )
        else:
            best_roi_value = None
            best_roi_names = []

        most_games_label = html.escape(", ".join(most_games_names))
        best_profit_label = html.escape(", ".join(best_profit_names))
        most_buy_in_label = html.escape(", ".join(most_buy_in_names))
        best_roi_label = html.escape(", ".join(best_roi_names))

        lines.append(
            f"Most games: <b>{most_games_label}</b> ({most_games_value})"
        )
        lines.append(
            f"Best profit: <b>{best_profit_label}</b> ({best_profit_value})"
        )
        lines.append(
            f"Most buy-in: <b>{most_buy_in_label}</b> ({most_buy_in_value})"
        )
        if best_roi_names:
            lines.append(
                f"Best ROI: <b>{best_roi_label}</b> ({best_roi_value:.2f}%)"
            )
    if summary.top_mvp_names:
        top_mvp_label = html.escape(", ".join(sorted(summary.top_mvp_names)))
        lines.append(
            f"Top MVP: <b>{top_mvp_label}</b> — "
            f"{summary.top_mvp_count} awards"
        )
    if summary.top_host_names:
        top_host_label = html.escape(", ".join(sorted(summary.top_host_names)))
        host_share = (
            (summary.top_host_games / summary.total_games) * 100
            if summary.total_games
            else 0
        )
        lines.append(
            f"Top host: <b>{top_host_label}</b> "
            f"({summary.top_host_games} games, {host_share:.1f}%)"
        )

    return "\n".join(lines)


async def get_group_game_report(
    game_id: int, name: str, roi: int, db_session: AsyncSession
) -> str:
    game: Game = await get_game_by_id(game_id, db_session)
    duration = format_duration(game.duration)
    text = texts["global_game_report"].format(
        game_id,
        duration,
        game.total_pot,
        name,
        roi,
    )
    return text


async def games_hosting_count(user_id: int, db_session: AsyncSession) -> int:
    query = select(Game).where(Game.host_id == user_id)
    result = await db_session.execute(query)
    return len(result.unique().scalars().all())


async def games_playing_count(user_id: int, db_session: AsyncSession) -> int:
    query = (
        select(Game)
        .join(Record, Game.id == Record.game_id)
        .where(Record.user_id == user_id)
    )
    result = await db_session.execute(query)
    return len(result.unique().scalars().all())


async def get_mvp_count(user_id: int, db_session: AsyncSession) -> int:
    query = select(Game).where(Game.mvp_id == user_id)
    result = await db_session.execute(query)
    return len(result.unique().scalars().all())


async def get_player_total_buy_in(user_id: int, db_session: AsyncSession) -> int:
    query = select(func.sum(Record.buy_in)).where(Record.user_id == user_id)
    result = await db_session.execute(query)
    total = result.scalar_one_or_none()
    return total or 0


async def get_player_total_buy_out(user_id: int, db_session: AsyncSession) -> int:
    query = select(func.sum(Record.buy_out)).where(Record.user_id == user_id)
    result = await db_session.execute(query)
    total = result.scalar_one_or_none()
    return total or 0
