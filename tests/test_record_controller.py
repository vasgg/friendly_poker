"""Tests for the record controller."""

from sqlalchemy.ext.asyncio import AsyncSession

from bot.controllers.record import (
    create_record,
    get_record,
    update_record,
    increase_player_buy_in,
    get_remained_players_in_game,
    check_game_balance,
    debt_calculator,
    update_net_profit_and_roi,
    get_mvp,
    get_roi_from_game_by_player_id,
)
from bot.internal.context import Amount, RecordUpdateMode
from database.models import User, Game, Record


class TestCreateRecord:
    async def test_creates_new_record(
        self, db_session: AsyncSession, sample_game: Game, multiple_users: list[User]
    ):
        result = await create_record(
            game_id=sample_game.id,
            user_id=multiple_users[0].id,
            db_session=db_session,
        )

        assert result.id is not None
        assert result.game_id == sample_game.id
        assert result.user_id == multiple_users[0].id
        assert result.buy_in is None
        assert result.buy_out is None


class TestGetRecord:
    async def test_returns_record_when_exists(
        self,
        db_session: AsyncSession,
        game_with_records: tuple[Game, list[Record]],
        multiple_users: list[User],
    ):
        game, records = game_with_records

        result = await get_record(game.id, multiple_users[0].id, db_session)

        assert result is not None
        assert result.game_id == game.id
        assert result.user_id == multiple_users[0].id

    async def test_returns_none_when_not_exists(
        self, db_session: AsyncSession, sample_game: Game
    ):
        result = await get_record(sample_game.id, 99999, db_session)

        assert result is None


class TestUpdateRecord:
    async def test_updates_buy_in(
        self,
        db_session: AsyncSession,
        game_with_records: tuple[Game, list[Record]],
        multiple_users: list[User],
    ):
        game, records = game_with_records

        result = await update_record(
            game_id=game.id,
            user_id=multiple_users[0].id,
            mode=RecordUpdateMode.UPDATE_BUY_IN,
            value=2500,
            db_session=db_session,
        )

        assert result is not None
        assert result.buy_in == 2500

    async def test_updates_buy_out(
        self,
        db_session: AsyncSession,
        game_with_records: tuple[Game, list[Record]],
        multiple_users: list[User],
    ):
        game, records = game_with_records

        result = await update_record(
            game_id=game.id,
            user_id=multiple_users[0].id,
            mode=RecordUpdateMode.UPDATE_BUY_OUT,
            value=3000,
            db_session=db_session,
        )

        assert result is not None
        assert result.buy_out == 3000

    async def test_returns_none_when_record_not_found(
        self, db_session: AsyncSession, sample_game: Game
    ):
        result = await update_record(
            game_id=sample_game.id,
            user_id=99999,
            mode=RecordUpdateMode.UPDATE_BUY_IN,
            value=1000,
            db_session=db_session,
        )

        assert result is None


class TestIncreasePlayerBuyIn:
    async def test_increases_buy_in_from_none(
        self, db_session: AsyncSession, sample_game: Game, multiple_users: list[User]
    ):
        record = Record(
            game_id=sample_game.id,
            user_id=multiple_users[0].id,
            buy_in=None,
        )
        db_session.add(record)
        await db_session.flush()

        await increase_player_buy_in(
            user_id=multiple_users[0].id,
            game_id=sample_game.id,
            amount=Amount.ONE_THOUSAND,
            db_session=db_session,
        )
        await db_session.refresh(record)

        assert record.buy_in == 1000

    async def test_increases_existing_buy_in(
        self, db_session: AsyncSession, sample_game: Game, multiple_users: list[User]
    ):
        record = Record(
            game_id=sample_game.id,
            user_id=multiple_users[0].id,
            buy_in=500,
        )
        db_session.add(record)
        await db_session.flush()

        await increase_player_buy_in(
            user_id=multiple_users[0].id,
            game_id=sample_game.id,
            amount=Amount.ONE_THOUSAND,
            db_session=db_session,
        )
        await db_session.refresh(record)

        assert record.buy_in == 1500


class TestGetRemainedPlayersInGame:
    async def test_returns_players_without_buyout(
        self,
        db_session: AsyncSession,
        sample_game: Game,
        multiple_users: list[User],
    ):
        record1 = Record(
            game_id=sample_game.id,
            user_id=multiple_users[0].id,
            buy_in=1000,
            buy_out=1500,
        )
        record2 = Record(
            game_id=sample_game.id,
            user_id=multiple_users[1].id,
            buy_in=1000,
            buy_out=None,
        )
        db_session.add_all([record1, record2])
        await db_session.flush()

        result = await get_remained_players_in_game(sample_game.id, db_session)

        assert "Player Two" in result
        assert "Player One" not in result

    async def test_returns_empty_when_all_have_buyout(
        self,
        db_session: AsyncSession,
        sample_game: Game,
        multiple_users: list[User],
    ):
        record = Record(
            game_id=sample_game.id,
            user_id=multiple_users[0].id,
            buy_in=1000,
            buy_out=1500,
        )
        db_session.add(record)
        await db_session.flush()

        result = await get_remained_players_in_game(sample_game.id, db_session)

        assert result == ""


class TestCheckGameBalance:
    async def test_returns_correct_balance_when_balanced(
        self,
        db_session: AsyncSession,
        sample_game: Game,
        multiple_users: list[User],
    ):
        record1 = Record(
            game_id=sample_game.id,
            user_id=multiple_users[0].id,
            buy_in=1000,
            buy_out=1500,
        )
        record2 = Record(
            game_id=sample_game.id,
            user_id=multiple_users[1].id,
            buy_in=1000,
            buy_out=500,
        )
        db_session.add_all([record1, record2])
        await db_session.flush()

        result = await check_game_balance(sample_game.id, db_session)

        assert result.total_pot == 2000
        assert result.delta == 0

    async def test_returns_positive_delta_when_short(
        self,
        db_session: AsyncSession,
        sample_game: Game,
        multiple_users: list[User],
    ):
        record1 = Record(
            game_id=sample_game.id,
            user_id=multiple_users[0].id,
            buy_in=1000,
            buy_out=500,
        )
        record2 = Record(
            game_id=sample_game.id,
            user_id=multiple_users[1].id,
            buy_in=1000,
            buy_out=400,
        )
        db_session.add_all([record1, record2])
        await db_session.flush()

        result = await check_game_balance(sample_game.id, db_session)

        assert result.total_pot == 2000
        assert result.delta == 1100


class TestDebtCalculator:
    async def test_calculates_debts_correctly(
        self,
        db_session: AsyncSession,
        sample_game: Game,
        multiple_users: list[User],
    ):
        record1 = Record(
            game_id=sample_game.id,
            user_id=multiple_users[0].id,
            buy_in=1000,
            buy_out=2000,
            net_profit=1000,
        )
        record2 = Record(
            game_id=sample_game.id,
            user_id=multiple_users[1].id,
            buy_in=1000,
            buy_out=0,
            net_profit=-1000,
        )
        db_session.add_all([record1, record2])
        await db_session.flush()

        result = await debt_calculator(sample_game.id, db_session)

        assert len(result) == 1
        assert result[0].amount == 1000

    async def test_returns_empty_when_no_debts(
        self,
        db_session: AsyncSession,
        sample_game: Game,
        multiple_users: list[User],
    ):
        record1 = Record(
            game_id=sample_game.id,
            user_id=multiple_users[0].id,
            buy_in=1000,
            buy_out=1000,
            net_profit=0,
        )
        db_session.add(record1)
        await db_session.flush()

        result = await debt_calculator(sample_game.id, db_session)

        assert result == []


class TestUpdateNetProfitAndRoi:
    async def test_updates_profit_and_roi(
        self,
        db_session: AsyncSession,
        sample_game: Game,
        multiple_users: list[User],
    ):
        record = Record(
            game_id=sample_game.id,
            user_id=multiple_users[0].id,
            buy_in=1000,
            buy_out=1500,
        )
        db_session.add(record)
        await db_session.flush()

        await update_net_profit_and_roi(sample_game.id, db_session)
        await db_session.refresh(record)

        assert record.net_profit == 500
        assert record.ROI == 50.0


class TestGetMvp:
    async def test_returns_player_with_highest_roi(
        self,
        db_session: AsyncSession,
        sample_game: Game,
        multiple_users: list[User],
    ):
        record1 = Record(
            game_id=sample_game.id,
            user_id=multiple_users[0].id,
            buy_in=1000,
            buy_out=1500,
            ROI=50.0,
        )
        record2 = Record(
            game_id=sample_game.id,
            user_id=multiple_users[1].id,
            buy_in=1000,
            buy_out=2000,
            ROI=100.0,
        )
        db_session.add_all([record1, record2])
        await db_session.flush()

        result = await get_mvp(sample_game.id, db_session)

        assert result == multiple_users[1].id

    async def test_returns_none_when_no_records(
        self, db_session: AsyncSession, sample_game: Game
    ):
        result = await get_mvp(sample_game.id, db_session)

        assert result is None


class TestGetRoiFromGameByPlayerId:
    async def test_returns_roi_for_player(
        self,
        db_session: AsyncSession,
        sample_game: Game,
        multiple_users: list[User],
    ):
        record = Record(
            game_id=sample_game.id,
            user_id=multiple_users[0].id,
            ROI=75.5,
        )
        db_session.add(record)
        await db_session.flush()

        result = await get_roi_from_game_by_player_id(
            sample_game.id, multiple_users[0].id, db_session
        )

        assert result == 75.5

    async def test_returns_none_when_no_record(
        self, db_session: AsyncSession, sample_game: Game
    ):
        result = await get_roi_from_game_by_player_id(sample_game.id, 99999, db_session)

        assert result is None
