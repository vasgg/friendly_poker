"""Shared test fixtures for controller tests."""

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from database.models import Base, User, Game, Record, Debt
from bot.internal.context import GameStatus


@pytest_asyncio.fixture
async def db_session():
    """Create an in-memory SQLite database session for testing."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session_factory() as session:
        yield session

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
    from datetime import datetime, UTC

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
            paid_at=datetime.now(UTC),
        ),
    ]
    for debt in debts:
        db_session.add(debt)
    await db_session.flush()
    return finished_game, debts
