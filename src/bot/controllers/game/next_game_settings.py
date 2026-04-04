from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from bot.controllers.game.crud import create_game
from database.models import Game, NextGameSettings

NEXT_GAME_SETTINGS_SINGLETON_ID = 1


@dataclass(frozen=True)
class NextGameSettingsSnapshot:
    ratio: int
    yearly_stats: bool
    version: int


async def _get_next_game_settings_row(
    db_session: AsyncSession, *, for_update: bool = False
) -> NextGameSettings:
    query = select(NextGameSettings).where(NextGameSettings.id == NEXT_GAME_SETTINGS_SINGLETON_ID)
    if for_update:
        query = query.with_for_update()
    result = await db_session.execute(query)
    settings = result.scalar_one_or_none()
    if settings is None:
        settings = NextGameSettings(id=NEXT_GAME_SETTINGS_SINGLETON_ID)
        db_session.add(settings)
        await db_session.flush()
    return settings


def _snapshot_from_row(settings: NextGameSettings) -> NextGameSettingsSnapshot:
    return NextGameSettingsSnapshot(
        ratio=settings.ratio,
        yearly_stats=settings.yearly_stats,
        version=settings.version,
    )


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


async def get_next_game_settings(db_session: AsyncSession) -> NextGameSettingsSnapshot:
    settings = await _get_next_game_settings_row(db_session)
    return _snapshot_from_row(settings)


async def update_next_game_ratio(
    *,
    ratio: int,
    expected_version: int,
    admin_id: int,
    admin_name: str | None,
    db_session: AsyncSession,
) -> NextGameSettingsSnapshot | None:
    query = (
        update(NextGameSettings)
        .where(
            NextGameSettings.id == NEXT_GAME_SETTINGS_SINGLETON_ID,
            NextGameSettings.version == expected_version,
        )
        .values(
            ratio=ratio,
            version=expected_version + 1,
            updated_by_admin_id=admin_id,
            updated_by_admin_name=admin_name,
            updated_at=_utcnow(),
        )
        .returning(
            NextGameSettings.ratio,
            NextGameSettings.yearly_stats,
            NextGameSettings.version,
        )
    )
    result = await db_session.execute(query)
    row = result.one_or_none()
    if row is None:
        return None
    return NextGameSettingsSnapshot(
        ratio=row.ratio,
        yearly_stats=row.yearly_stats,
        version=row.version,
    )


async def update_next_game_yearly_stats(
    *,
    enabled: bool,
    expected_version: int,
    admin_id: int,
    admin_name: str | None,
    db_session: AsyncSession,
) -> NextGameSettingsSnapshot | None:
    query = (
        update(NextGameSettings)
        .where(
            NextGameSettings.id == NEXT_GAME_SETTINGS_SINGLETON_ID,
            NextGameSettings.version == expected_version,
        )
        .values(
            yearly_stats=enabled,
            version=expected_version + 1,
            updated_by_admin_id=admin_id,
            updated_by_admin_name=admin_name,
            updated_at=_utcnow(),
        )
        .returning(
            NextGameSettings.ratio,
            NextGameSettings.yearly_stats,
            NextGameSettings.version,
        )
    )
    result = await db_session.execute(query)
    row = result.one_or_none()
    if row is None:
        return None
    return NextGameSettingsSnapshot(
        ratio=row.ratio,
        yearly_stats=row.yearly_stats,
        version=row.version,
    )


async def consume_next_game_settings_for_new_game(
    *,
    admin_id: int,
    host_id: int,
    db_session: AsyncSession,
) -> tuple[Game | None, NextGameSettingsSnapshot]:
    settings = await _get_next_game_settings_row(db_session, for_update=True)
    snapshot = _snapshot_from_row(settings)
    game = await create_game(
        admin_id=admin_id,
        host_id=host_id,
        ratio=snapshot.ratio,
        send_yearly_stats_on_finish=snapshot.yearly_stats,
        db_session=db_session,
    )
    if game is None:
        return None, snapshot

    settings.ratio = 1
    settings.yearly_stats = False
    settings.version += 1
    settings.updated_by_admin_id = None
    settings.updated_by_admin_name = None
    settings.updated_at = None
    await db_session.flush()
    return game, snapshot
