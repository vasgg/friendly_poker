from datetime import datetime
import logging

from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from bot.config import settings
from bot.internal.lexicon import texts
from bot.internal.context import GameStatus
from database.models import Game, Record

logger = logging.getLogger(__name__)


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


async def create_game(admin_id: int, host_id: int, db_session: AsyncSession) -> Game:
    new_game = Game(
        admin_id=admin_id,
        host_id=host_id,
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
