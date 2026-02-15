import logging
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from bot.internal.context import GameStatus
from database.models import Game

logger = logging.getLogger(__name__)


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
        logger.error("Found %s active games! Returning the most recent one.", len(games))

    game = games[0]
    logger.info(
        "Active game: id=%s host_id=%s players=%s",
        game.id,
        game.host_id,
        len(game.records),
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
    logger.info("New game created: id=%s host_id=%s", new_game.id, new_game.host_id)
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

