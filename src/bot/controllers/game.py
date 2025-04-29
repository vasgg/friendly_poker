from datetime import datetime
import logging

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from bot.config import settings
from bot.internal.dicts import texts
from bot.internal.context import GameStatus
from database.models import Game

logger = logging.getLogger(__name__)


async def get_active_game(db_session: AsyncSession) -> Game | None:
    query = (
        select(Game)
        .where(Game.status == GameStatus.ACTIVE)
        .order_by(Game.created_at.desc())
        .options(joinedload(Game.records))
    )
    result = await db_session.execute(query)
    game = result.unique().scalar_one_or_none()
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
    game: Game = await get_active_game(db_session)

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
