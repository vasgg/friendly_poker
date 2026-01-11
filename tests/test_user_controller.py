"""Tests for the user controller."""

from unittest.mock import MagicMock
from sqlalchemy.ext.asyncio import AsyncSession

from bot.controllers.user import (
    add_user_to_db,
    get_user_from_db_by_tg_id,
    get_all_users,
    get_last_played_users,
    get_players_from_game,
    get_unplayed_users,
    get_users_with_buyout,
    ask_next_question,
)
from database.models import User, Game, Record


class TestGetUserFromDbByTgId:
    async def test_returns_user_when_exists(
        self, db_session: AsyncSession, sample_user: User
    ):
        result = await get_user_from_db_by_tg_id(sample_user.id, db_session)

        assert result is not None
        assert result.id == sample_user.id
        assert result.fullname == "Test User"

    async def test_returns_none_when_not_exists(self, db_session: AsyncSession):
        result = await get_user_from_db_by_tg_id(999999, db_session)

        assert result is None


class TestAddUserToDb:
    async def test_creates_new_user(self, db_session: AsyncSession):
        aiogram_user = MagicMock()
        aiogram_user.id = 111222333
        aiogram_user.full_name = "New User"
        aiogram_user.username = "newuser"

        result = await add_user_to_db(aiogram_user, db_session)

        assert result.id == 111222333
        assert result.fullname == "New User"
        assert result.username == "newuser"
        assert result.is_admin is False

    async def test_creates_admin_user(self, db_session: AsyncSession):
        aiogram_user = MagicMock()
        aiogram_user.id = 444555666
        aiogram_user.full_name = "Admin"
        aiogram_user.username = "admin"

        result = await add_user_to_db(aiogram_user, db_session, is_admin=True)

        assert result.is_admin is True


class TestGetAllUsers:
    async def test_returns_all_users(
        self, db_session: AsyncSession, multiple_users: list[User]
    ):
        result = await get_all_users(db_session)

        assert len(result) == 4
        ids = [u.id for u in result]
        assert 1 in ids
        assert 2 in ids
        assert 3 in ids
        assert 4 in ids

    async def test_returns_empty_list_when_no_users(self, db_session: AsyncSession):
        result = await get_all_users(db_session)

        assert result == []


class TestGetLastPlayedUsers:
    async def test_returns_users_who_played_last(
        self, db_session: AsyncSession, multiple_users: list[User]
    ):
        multiple_users[0].last_time_played = True
        multiple_users[1].last_time_played = True
        multiple_users[2].last_time_played = False
        await db_session.flush()

        result = await get_last_played_users(db_session)

        assert len(result) == 2
        assert 1 in result
        assert 2 in result
        assert 3 not in result

    async def test_returns_empty_when_none_played(
        self, db_session: AsyncSession, multiple_users: list[User]
    ):
        result = await get_last_played_users(db_session)

        assert result == []


class TestGetUnplayedUsers:
    async def test_returns_users_who_didnt_play_last(
        self, db_session: AsyncSession, multiple_users: list[User]
    ):
        multiple_users[0].last_time_played = True
        multiple_users[1].last_time_played = False
        await db_session.flush()

        result = await get_unplayed_users(db_session)

        user_ids = [u.id for u in result]
        assert 1 not in user_ids
        assert 2 in user_ids


class TestGetPlayersFromGame:
    async def test_returns_players_in_game(
        self,
        db_session: AsyncSession,
        game_with_records: tuple[Game, list[Record]],
        multiple_users: list[User],
    ):
        game, records = game_with_records

        result = await get_players_from_game(game.id, db_session)

        assert len(result) == 3
        user_ids = [u.id for u in result]
        assert multiple_users[0].id in user_ids
        assert multiple_users[1].id in user_ids
        assert multiple_users[2].id in user_ids

    async def test_returns_empty_for_game_without_players(
        self, db_session: AsyncSession, sample_game: Game
    ):
        result = await get_players_from_game(sample_game.id, db_session)

        assert result == []


class TestGetUsersWithBuyout:
    async def test_returns_users_with_nonzero_buyout(
        self,
        db_session: AsyncSession,
        game_with_records: tuple[Game, list[Record]],
    ):
        game, records = game_with_records

        result = await get_users_with_buyout(game.id, db_session)

        assert len(result) == 2


class TestAskNextQuestion:
    async def test_returns_first_missing_field(self, sample_user: User):
        sample_user.IBAN = None
        sample_user.bank = None
        sample_user.name_surname = None

        field, question = await ask_next_question(sample_user)

        assert field is not None
        assert question is not None

    async def test_returns_none_when_all_filled(self, sample_user: User):
        sample_user.IBAN = "GB123456789"
        sample_user.bank = "Test Bank"
        sample_user.name_surname = "Test Name"

        field, question = await ask_next_question(sample_user)

        assert field is None
        assert question is None
