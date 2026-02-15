import html
import logging
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import extract, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from bot.internal.context import GameStatus
from bot.internal.lexicon import texts
from database.models import Game, Record, User

logger = logging.getLogger(__name__)


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


async def get_active_game(db_session: AsyncSession) -> Game | None:
    query = (
        select(Game)
        .where(Game.status == GameStatus.ACTIVE)
        .options(joinedload(Game.records))
        .order_by(Game.id.desc())
        .limit(2)
    )
    result = await db_session.execute(query)
    games = result.unique().scalars().all()
    if not games:
        return None

    if len(games) > 1:
        logger.error(f"Found {len(games)} active games! Returning the most recent one.")

    game = games[0]
    if game:
        logger.info(
            f"Active game: {game.id=}, {game.host_id=}, players: {len(game.records)}"
        )
    return game


async def get_game_by_id(game_id: int, db_session: AsyncSession) -> Game | None:
    query = select(Game).where(Game.id == game_id)
    result = await db_session.execute(query)
    return result.unique().scalar_one_or_none()


async def create_game(
    admin_id: int, host_id: int, db_session: AsyncSession, ratio: int = 1
) -> Game | None:
    existing = await get_active_game(db_session)
    if existing is not None:
        logger.warning("Cannot create game: active game %s already exists", existing.id)
        return None
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
    now = datetime.now(UTC)
    game = await get_game_by_id(game_id, db_session)
    if game is None:
        return
    start_time = game.created_at
    if start_time.tzinfo is None:
        start_time = start_time.replace(tzinfo=UTC)
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


async def _get_stats(
    year: int | None, db_session: AsyncSession
) -> tuple[YearlySummary, list[YearlyPlayerStats]]:
    def with_year_filter(query):
        if year is None:
            return query
        return query.where(extract("year", Game.created_at) == year)

    summary_query = with_year_filter(
        select(
            func.count(func.distinct(Game.id)).label("games_count"),
            func.count(func.distinct(Record.user_id)).label("players_count"),
            func.coalesce(func.sum(Record.buy_in), 0).label("total_buy_in"),
        )
        .join(Record, Record.game_id == Game.id)
        .where(Game.status == GameStatus.FINISHED)
    )
    summary_result = await db_session.execute(summary_query)
    total_games, total_players, total_buy_in = summary_result.one()

    duration_query = with_year_filter(
        select(func.coalesce(func.sum(Game.duration), 0)).where(
            Game.status == GameStatus.FINISHED
        )
    )
    duration_result = await db_session.execute(duration_query)
    (total_duration_seconds,) = duration_result.one()

    biggest_pot_query = with_year_filter(
        select(Game.total_pot, Game.id)
        .where(Game.status == GameStatus.FINISHED)
        .order_by(Game.total_pot.desc(), Game.id.asc())
        .limit(1)
    )
    biggest_pot_result = await db_session.execute(biggest_pot_query)
    biggest_pot_row = biggest_pot_result.one_or_none()
    if biggest_pot_row:
        biggest_pot, biggest_pot_game_id = biggest_pot_row
    else:
        biggest_pot, biggest_pot_game_id = 0, None

    players_query = with_year_filter(
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

    host_query = with_year_filter(
        select(
            User.fullname,
            func.count(Game.id).label("games_hosted"),
        )
        .join(Game, Game.host_id == User.id)
        .where(Game.status == GameStatus.FINISHED)
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

    single_roi_query = with_year_filter(
        select(func.max(Record.ROI))
        .join(Game, Game.id == Record.game_id)
        .where(Game.status == GameStatus.FINISHED)
        .where(Record.ROI.isnot(None))
    )
    single_roi_result = await db_session.execute(single_roi_query)
    (best_single_game_roi,) = single_roi_result.one()
    if best_single_game_roi is not None:
        single_roi_names_query = with_year_filter(
            select(func.distinct(User.fullname))
            .join(Record, Record.user_id == User.id)
            .join(Game, Game.id == Record.game_id)
            .where(Game.status == GameStatus.FINISHED)
            .where(Record.ROI == best_single_game_roi)  # noqa: SIM300
        )
        single_roi_names_result = await db_session.execute(single_roi_names_query)
        best_single_game_roi_names = sorted(
            row[0] for row in single_roi_names_result.all()
        )
    else:
        best_single_game_roi_names = []

    mvp_query = with_year_filter(
        select(
            User.fullname,
            func.count(Game.id).label("mvp_count"),
        )
        .join(Game, Game.mvp_id == User.id)
        .where(Game.status == GameStatus.FINISHED)
        .where(Game.mvp_id.isnot(None))
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
        biggest_pot=biggest_pot or 0,
        biggest_pot_game_id=biggest_pot_game_id,
        total_buy_in=total_buy_in or 0,
        total_duration_seconds=total_duration_seconds or 0,
        best_single_game_roi=best_single_game_roi,
        best_single_game_roi_names=best_single_game_roi_names,
        top_mvp_names=top_mvp_names,
        top_mvp_count=top_mvp_count or 0,
        top_host_names=top_host_names,
        top_host_games=top_host_games or 0,
    )

    return summary, players_stats


async def get_yearly_stats(
    year: int, db_session: AsyncSession
) -> tuple[YearlySummary, list[YearlyPlayerStats]]:
    return await _get_stats(year, db_session)


async def get_all_time_stats(
    db_session: AsyncSession,
) -> tuple[YearlySummary, list[YearlyPlayerStats]]:
    return await _get_stats(None, db_session)


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
        best_profit_names = sorted(
            p.fullname for p in players if p.net == best_profit_value
        )
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

        lines.append(
            f"Most games: <b>{most_games_label}</b> ({most_games_value})"
        )
        lines.append(
            f"Best profit: <b>{best_profit_label}</b> ({best_profit_value})"
        )
        lines.append(
            f"Most buy-in: <b>{most_buy_in_label}</b> ({most_buy_in_value})"
        )
        if summary.best_single_game_roi_names:
            best_single_roi_label = html.escape(
                ", ".join(summary.best_single_game_roi_names)
            )
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
    text = texts["global_game_report"].format(
        game_id,
        duration,
        game.total_pot or 0,
        name,
        roi,
    )
    return text


async def games_hosting_count(user_id: int, db_session: AsyncSession) -> int:
    query = select(func.count()).select_from(Game).where(Game.host_id == user_id)
    result = await db_session.execute(query)
    return result.scalar_one()


async def games_playing_count(user_id: int, db_session: AsyncSession) -> int:
    query = (
        select(func.count(func.distinct(Game.id)))
        .join(Record, Game.id == Record.game_id)
        .where(Record.user_id == user_id)
    )
    result = await db_session.execute(query)
    return result.scalar_one()


async def get_mvp_count(user_id: int, db_session: AsyncSession) -> int:
    query = select(func.count()).select_from(Game).where(Game.mvp_id == user_id)
    result = await db_session.execute(query)
    return result.scalar_one()


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
