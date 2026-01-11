"""Tests for the game controller."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from bot.controllers.game import (
    get_active_game,
    get_game_by_id,
    create_game,
    abort_game,
    commit_game_results_to_db,
    games_hosting_count,
    games_playing_count,
    get_mvp_count,
    get_player_total_buy_in,
    get_player_total_buy_out,
    format_duration,
    format_duration_with_days,
)
from bot.internal.context import GameStatus
from database.models import User, Game, Record


class TestGetActiveGame:
    async def test_returns_active_game(
        self, db_session: AsyncSession, sample_game: Game
    ):
        result = await get_active_game(db_session)

        assert result is not None
        assert result.id == sample_game.id
        assert result.status == GameStatus.ACTIVE

    async def test_returns_none_when_no_active_game(
        self, db_session: AsyncSession, finished_game: Game
    ):
        result = await get_active_game(db_session)

        assert result is None

    async def test_returns_most_recent_when_multiple_active(
        self, db_session: AsyncSession, multiple_users: list[User]
    ):
        game1 = Game(
            admin_id=multiple_users[0].id,
            host_id=multiple_users[1].id,
            status=GameStatus.ACTIVE,
        )
        game2 = Game(
            admin_id=multiple_users[0].id,
            host_id=multiple_users[1].id,
            status=GameStatus.ACTIVE,
        )
        db_session.add_all([game1, game2])
        await db_session.flush()

        result = await get_active_game(db_session)

        assert result is not None
        assert result.id == game2.id


class TestGetGameById:
    async def test_returns_game_when_exists(
        self, db_session: AsyncSession, sample_game: Game
    ):
        result = await get_game_by_id(sample_game.id, db_session)

        assert result is not None
        assert result.id == sample_game.id

    async def test_returns_none_when_not_exists(self, db_session: AsyncSession):
        result = await get_game_by_id(99999, db_session)

        assert result is None


class TestCreateGame:
    async def test_creates_new_game(
        self, db_session: AsyncSession, multiple_users: list[User]
    ):
        result = await create_game(
            admin_id=multiple_users[0].id,
            host_id=multiple_users[1].id,
            db_session=db_session,
        )

        assert result.id is not None
        assert result.admin_id == multiple_users[0].id
        assert result.host_id == multiple_users[1].id
        assert result.status == GameStatus.ACTIVE
        assert result.ratio == 1

    async def test_creates_game_with_custom_ratio(
        self, db_session: AsyncSession, multiple_users: list[User]
    ):
        result = await create_game(
            admin_id=multiple_users[0].id,
            host_id=multiple_users[1].id,
            db_session=db_session,
            ratio=2,
        )

        assert result.ratio == 2


class TestAbortGame:
    async def test_sets_game_status_to_aborted(
        self, db_session: AsyncSession, sample_game: Game
    ):
        await abort_game(sample_game.id, db_session)
        await db_session.refresh(sample_game)

        assert sample_game.status == GameStatus.ABORTED


class TestCommitGameResultsToDb:
    async def test_updates_game_with_results(
        self, db_session: AsyncSession, sample_game: Game, multiple_users: list[User]
    ):
        await commit_game_results_to_db(
            game_id=sample_game.id,
            total_pot=5000,
            mvp_id=multiple_users[0].id,
            db_session=db_session,
        )
        await db_session.refresh(sample_game)

        assert sample_game.status == GameStatus.FINISHED
        assert sample_game.total_pot == 5000
        assert sample_game.mvp_id == multiple_users[0].id
        assert sample_game.duration is not None


class TestGamesHostingCount:
    async def test_returns_count_of_hosted_games(
        self, db_session: AsyncSession, multiple_users: list[User]
    ):
        for _ in range(3):
            game = Game(
                admin_id=multiple_users[0].id,
                host_id=multiple_users[1].id,
            )
            db_session.add(game)
        await db_session.flush()

        result = await games_hosting_count(multiple_users[1].id, db_session)

        assert result == 3

    async def test_returns_zero_when_no_hosted_games(
        self, db_session: AsyncSession, multiple_users: list[User]
    ):
        result = await games_hosting_count(multiple_users[0].id, db_session)

        assert result == 0


class TestGamesPlayingCount:
    async def test_returns_count_of_games_played(
        self,
        db_session: AsyncSession,
        game_with_records: tuple[Game, list[Record]],
        multiple_users: list[User],
    ):
        result = await games_playing_count(multiple_users[0].id, db_session)

        assert result == 1

    async def test_returns_zero_when_no_games_played(
        self, db_session: AsyncSession, multiple_users: list[User]
    ):
        result = await games_playing_count(multiple_users[3].id, db_session)

        assert result == 0


class TestGetMvpCount:
    async def test_returns_mvp_count(
        self, db_session: AsyncSession, multiple_users: list[User]
    ):
        for _ in range(2):
            game = Game(
                admin_id=multiple_users[0].id,
                host_id=multiple_users[1].id,
                mvp_id=multiple_users[0].id,
                status=GameStatus.FINISHED,
            )
            db_session.add(game)
        await db_session.flush()

        result = await get_mvp_count(multiple_users[0].id, db_session)

        assert result == 2

    async def test_returns_zero_when_never_mvp(
        self, db_session: AsyncSession, multiple_users: list[User]
    ):
        result = await get_mvp_count(multiple_users[3].id, db_session)

        assert result == 0


class TestGetPlayerTotalBuyIn:
    async def test_returns_total_buy_in(
        self,
        db_session: AsyncSession,
        game_with_records: tuple[Game, list[Record]],
        multiple_users: list[User],
    ):
        result = await get_player_total_buy_in(multiple_users[0].id, db_session)

        assert result == 1000

    async def test_returns_zero_when_no_records(
        self, db_session: AsyncSession, multiple_users: list[User]
    ):
        result = await get_player_total_buy_in(multiple_users[3].id, db_session)

        assert result == 0


class TestGetPlayerTotalBuyOut:
    async def test_returns_total_buy_out(
        self,
        db_session: AsyncSession,
        game_with_records: tuple[Game, list[Record]],
        multiple_users: list[User],
    ):
        result = await get_player_total_buy_out(multiple_users[0].id, db_session)

        assert result == 1500

    async def test_returns_zero_when_no_records(
        self, db_session: AsyncSession, multiple_users: list[User]
    ):
        result = await get_player_total_buy_out(multiple_users[3].id, db_session)

        assert result == 0


class TestFormatDuration:
    @pytest.mark.parametrize(
        "seconds,expected",
        [
            (3600, "1h 0m"),
            (7200, "2h 0m"),
            (3660, "1h 1m"),
            (30, "0m"),
            (90, "1m"),
            (5400, "1h 30m"),
        ],
    )
    def test_formats_duration_correctly(self, seconds: int, expected: str):
        result = format_duration(seconds)
        assert result == expected


class TestFormatDurationWithDays:
    @pytest.mark.parametrize(
        "seconds,expected",
        [
            (3600, "1h 0m"),
            (86400, "1d 0h 0m"),
            (90000, "1d 1h 0m"),
            (30, "0m"),
            (90, "1m"),
            (172800, "2d 0h 0m"),
        ],
    )
    def test_formats_duration_with_days_correctly(self, seconds: int, expected: str):
        result = format_duration_with_days(seconds)
        assert result == expected
