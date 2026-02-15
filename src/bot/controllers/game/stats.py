import logging

from sqlalchemy import extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.controllers.game.types import YearlyPlayerStats, YearlySummary
from bot.internal.context import GameStatus
from database.models import Game, Record, User

logger = logging.getLogger(__name__)


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
        best_single_game_roi_names = sorted(row[0] for row in single_roi_names_result.all())
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
