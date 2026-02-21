import logging
from dataclasses import dataclass

from aiogram import Bot
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import settings
from bot.internal.context import GameStatus
from database.models import Debt, Game, Record, User

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class HardAbortResult:
    game_id: int
    start_message_id: int | None
    start_message_deleted: bool | None
    start_message_delete_error: str | None
    records_deleted: int
    debts_deleted: int
    affected_player_ids: list[int]
    last_time_played_restored_from_game_id: int | None


async def _restore_last_time_played(db_session: AsyncSession) -> int | None:
    active_game_id_result = await db_session.execute(
        select(Game.id)
        .where(Game.status == GameStatus.ACTIVE)
        .order_by(Game.id.desc())
        .limit(1)
    )
    source_game_id = active_game_id_result.scalar_one_or_none()
    if source_game_id is None:
        last_finished_game_result = await db_session.execute(
            select(Game.id)
            .where(Game.status == GameStatus.FINISHED)
            .order_by(Game.id.desc())
            .limit(1)
        )
        source_game_id = last_finished_game_result.scalar_one_or_none()

    await db_session.execute(update(User).values(last_time_played=False))
    if source_game_id is None:
        return None

    player_ids_result = await db_session.execute(
        select(Record.user_id).where(Record.game_id == source_game_id)
    )
    player_ids = sorted(set(player_ids_result.scalars().all()))
    if player_ids:
        await db_session.execute(
            update(User).where(User.id.in_(player_ids)).values(last_time_played=True)
        )
    return source_game_id


async def hard_abort_game(game_id: int, bot: Bot, db_session: AsyncSession) -> HardAbortResult:
    game_result = await db_session.execute(
        select(Game.message_id).where(Game.id == game_id)
    )
    start_message_id = game_result.scalar_one_or_none()

    players_result = await db_session.execute(
        select(Record.user_id).where(Record.game_id == game_id)
    )
    affected_player_ids = sorted(set(players_result.scalars().all()))

    debts_delete_result = await db_session.execute(
        delete(Debt).where(Debt.game_id == game_id)
    )
    debts_deleted = debts_delete_result.rowcount or 0

    records_delete_result = await db_session.execute(
        delete(Record).where(Record.game_id == game_id)
    )
    records_deleted = records_delete_result.rowcount or 0

    await db_session.execute(delete(Game).where(Game.id == game_id))

    for player_id in affected_player_ids:
        games_played_result = await db_session.execute(
            select(func.count()).select_from(Record).where(Record.user_id == player_id)
        )
        games_played = games_played_result.scalar_one()
        await db_session.execute(
            update(User).where(User.id == player_id).values(games_played=games_played)
        )

    restored_from_game_id = await _restore_last_time_played(db_session)
    await db_session.commit()

    start_message_deleted = None
    start_message_delete_error = None
    if start_message_id:
        try:
            await bot.delete_message(
                chat_id=settings.bot.GROUP_ID,
                message_id=start_message_id,
            )
            start_message_deleted = True
            logger.info(
                "Game %s: deleted group start message %s",
                game_id,
                start_message_id,
            )
        except Exception as exc:
            start_message_deleted = False
            start_message_delete_error = f"{type(exc).__name__}: {exc}"
            logger.warning(
                "Game %s: failed to delete group start message %s - %s",
                game_id,
                start_message_id,
                start_message_delete_error,
            )

    logger.info(
        "Game hard-aborted: id=%s records_deleted=%s debts_deleted=%s players=%s "
        "last_time_played_restored_from=%s",
        game_id,
        records_deleted,
        debts_deleted,
        len(affected_player_ids),
        restored_from_game_id,
    )
    return HardAbortResult(
        game_id=game_id,
        start_message_id=start_message_id,
        start_message_deleted=start_message_deleted,
        start_message_delete_error=start_message_delete_error,
        records_deleted=records_deleted,
        debts_deleted=debts_deleted,
        affected_player_ids=affected_player_ids,
        last_time_played_restored_from_game_id=restored_from_game_id,
    )

