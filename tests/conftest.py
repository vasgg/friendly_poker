"""Shared test fixtures for controller tests."""

import os
from datetime import UTC, datetime
from pathlib import Path

import pytest
import pytest_asyncio
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from alembic import command
from bot.internal.context import GameStatus
from database.models import Debt, Game, Record, User

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_TRUNCATE_TEST_TABLES_SQL = text(
    """
    DO $$
    DECLARE
        tables_to_truncate text;
    BEGIN
        SELECT string_agg(format('%I', tablename), ', ')
        INTO tables_to_truncate
        FROM pg_tables
        WHERE schemaname = 'public'
          AND tablename <> 'alembic_version';

        IF tables_to_truncate IS NOT NULL THEN
            EXECUTE 'TRUNCATE TABLE ' || tables_to_truncate || ' RESTART IDENTITY CASCADE';
        END IF;
    END $$;
    """
)


def _build_alembic_config(test_db_url: str) -> Config:
    """Build Alembic config pointing to project-local migration scripts."""
    config = Config(str(_PROJECT_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(_PROJECT_ROOT / "alembic"))
    config.set_main_option("sqlalchemy.url", test_db_url)
    return config


@pytest.fixture(scope="session")
def migrated_test_db_url() -> str:
    """Ensure schema is created via Alembic and return test DB URL."""
    test_db_url = os.getenv("TEST_DB_URL")
    if not test_db_url:
        raise pytest.skip.Exception("Set TEST_DB_URL to run database tests")

    previous_db_url = os.environ.get("DB_URL")
    os.environ["DB_URL"] = test_db_url
    try:
        command.upgrade(_build_alembic_config(test_db_url), "head")
    finally:
        if previous_db_url is None:
            os.environ.pop("DB_URL", None)
        else:
            os.environ["DB_URL"] = previous_db_url

    return test_db_url


@pytest_asyncio.fixture
async def db_session(migrated_test_db_url: str):
    """Create isolated PostgreSQL session on Alembic-managed schema."""
    engine = create_async_engine(
        migrated_test_db_url,
        echo=False,
    )

    async with engine.begin() as conn:
        await conn.execute(_TRUNCATE_TEST_TABLES_SQL)

    async_session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    try:
        async with async_session_factory() as session:
            yield session
    finally:
        async with engine.begin() as conn:
            await conn.execute(_TRUNCATE_TEST_TABLES_SQL)
        await engine.dispose()


@pytest_asyncio.fixture
async def sample_user(db_session: AsyncSession) -> User:
    """Create a sample user for testing."""
    user = User(
        id=123456789,
        fullname="Test User",
        username="testuser",
        is_admin=False,
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest_asyncio.fixture
async def admin_user(db_session: AsyncSession) -> User:
    """Create an admin user for testing."""
    user = User(
        id=987654321,
        fullname="Admin User",
        username="adminuser",
        is_admin=True,
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest_asyncio.fixture
async def multiple_users(db_session: AsyncSession) -> list[User]:
    """Create multiple users for testing."""
    users = [
        User(id=1, fullname="Player One", username="player1"),
        User(id=2, fullname="Player Two", username="player2"),
        User(id=3, fullname="Player Three", username="player3"),
        User(id=4, fullname="Player Four", username=None),
    ]
    for user in users:
        db_session.add(user)
    await db_session.flush()
    return users


@pytest_asyncio.fixture
async def sample_game(db_session: AsyncSession, multiple_users: list[User]) -> Game:
    """Create a sample active game for testing."""
    game = Game(
        admin_id=multiple_users[0].id,
        host_id=multiple_users[1].id,
        status=GameStatus.ACTIVE,
        ratio=1,
    )
    db_session.add(game)
    await db_session.flush()
    return game


@pytest_asyncio.fixture
async def finished_game(db_session: AsyncSession, multiple_users: list[User]) -> Game:
    """Create a finished game for testing."""
    game = Game(
        admin_id=multiple_users[0].id,
        host_id=multiple_users[1].id,
        status=GameStatus.FINISHED,
        total_pot=10000,
        mvp_id=multiple_users[0].id,
        duration=7200,
        ratio=1,
    )
    db_session.add(game)
    await db_session.flush()
    return game


@pytest_asyncio.fixture
async def game_with_records(
    db_session: AsyncSession,
    sample_game: Game,
    multiple_users: list[User],
) -> tuple[Game, list[Record]]:
    """Create a game with player records."""
    records = []
    for i, user in enumerate(multiple_users[:3]):
        record = Record(
            game_id=sample_game.id,
            user_id=user.id,
            buy_in=1000 * (i + 1),
            buy_out=1500 * (i + 1) if i < 2 else 0,
        )
        db_session.add(record)
        records.append(record)
    await db_session.flush()
    return sample_game, records


@pytest_asyncio.fixture
async def game_with_debts(
    db_session: AsyncSession,
    finished_game: Game,
    multiple_users: list[User],
) -> tuple[Game, list[Debt]]:
    """Create a finished game with debts."""
    debts = [
        Debt(
            game_id=finished_game.id,
            creditor_id=multiple_users[0].id,
            debtor_id=multiple_users[1].id,
            amount=500,
            is_paid=False,
        ),
        Debt(
            game_id=finished_game.id,
            creditor_id=multiple_users[0].id,
            debtor_id=multiple_users[2].id,
            amount=300,
            is_paid=True,
            paid_at=datetime.now(UTC).replace(tzinfo=None),
        ),
    ]
    for debt in debts:
        db_session.add(debt)
    await db_session.flush()
    return finished_game, debts
