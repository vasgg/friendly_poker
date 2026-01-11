"""Tests for the debt controller."""

from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from bot.controllers.debt import (
    get_debts,
    get_debts_with_users,
    calculate_debt_amount,
    equalizer,
    flush_debts_to_db,
    mark_debt_as_paid,
    get_debt_by_id,
    get_unpaid_debts_as_debtor,
    get_unpaid_debts_as_creditor,
)
from database.models import User, Game, Debt


class TestGetDebts:
    async def test_returns_debts_for_game(
        self,
        db_session: AsyncSession,
        game_with_debts: tuple[Game, list[Debt]],
    ):
        game, debts = game_with_debts

        result = await get_debts(game.id, db_session)

        assert len(result) == 2

    async def test_returns_empty_when_no_debts(
        self, db_session: AsyncSession, sample_game: Game
    ):
        result = await get_debts(sample_game.id, db_session)

        assert result == []


class TestGetDebtsWithUsers:
    async def test_returns_debts_with_users_loaded(
        self,
        db_session: AsyncSession,
        game_with_debts: tuple[Game, list[Debt]],
    ):
        game, debts = game_with_debts

        result = await get_debts_with_users(game.id, db_session)

        assert len(result) == 2
        for debt in result:
            assert debt.creditor is not None
            assert debt.debtor is not None

    async def test_returns_empty_when_no_debts(
        self, db_session: AsyncSession, sample_game: Game
    ):
        result = await get_debts_with_users(sample_game.id, db_session)

        assert result == []


class TestCalculateDebtAmount:
    @pytest.mark.parametrize(
        "amount,ratio,expected",
        [
            (1000, 1, Decimal("10.00")),
            (1000, 2, Decimal("20.00")),
            (500, 1, Decimal("5.00")),
            (333, 1, Decimal("3.33")),
            (555, 3, Decimal("16.65")),
            (0, 1, Decimal("0.00")),
        ],
    )
    def test_calculates_debt_correctly(
        self, amount: int, ratio: int, expected: Decimal
    ):
        result = calculate_debt_amount(amount, ratio)

        assert result == expected


class TestEqualizer:
    def test_calculates_single_debt(self):
        balance_map = {1: 1000, 2: -1000}

        result = equalizer(balance_map, game_id=1)

        assert len(result) == 1
        assert result[0].debtor_id == 2
        assert result[0].creditor_id == 1
        assert result[0].amount == 1000

    def test_calculates_multiple_debts(self):
        balance_map = {1: 500, 2: 500, 3: -1000}

        result = equalizer(balance_map, game_id=1)

        assert len(result) == 2
        total_amount = sum(d.amount for d in result)
        assert total_amount == 1000

    def test_returns_empty_when_all_balanced(self):
        balance_map = {1: 0, 2: 0, 3: 0}

        result = equalizer(balance_map, game_id=1)

        assert result == []

    def test_returns_empty_for_empty_map(self):
        result = equalizer({}, game_id=1)

        assert result == []

    def test_minimizes_transactions(self):
        balance_map = {1: 1000, 2: -500, 3: -500}

        result = equalizer(balance_map, game_id=1)

        assert len(result) == 2

    def test_complex_scenario(self):
        balance_map = {1: 300, 2: 200, 3: -100, 4: -400}

        result = equalizer(balance_map, game_id=1)

        creditor_total = sum(
            d.amount for d in result if d.creditor_id in [1, 2]
        )
        debtor_total = sum(
            d.amount for d in result if d.debtor_id in [3, 4]
        )
        assert creditor_total == debtor_total


class TestFlushDebtsToDb:
    async def test_saves_debts_to_database(
        self,
        db_session: AsyncSession,
        finished_game: Game,
        multiple_users: list[User],
    ):
        debts = [
            Debt(
                game_id=finished_game.id,
                creditor_id=multiple_users[0].id,
                debtor_id=multiple_users[1].id,
                amount=500,
            ),
            Debt(
                game_id=finished_game.id,
                creditor_id=multiple_users[0].id,
                debtor_id=multiple_users[2].id,
                amount=300,
            ),
        ]

        await flush_debts_to_db(debts, db_session)

        result = await get_debts(finished_game.id, db_session)
        assert len(result) == 2

    async def test_handles_empty_list(self, db_session: AsyncSession):
        await flush_debts_to_db([], db_session)


class TestMarkDebtAsPaid:
    async def test_marks_debt_as_paid(
        self,
        db_session: AsyncSession,
        game_with_debts: tuple[Game, list[Debt]],
    ):
        game, debts = game_with_debts
        unpaid_debt = debts[0]

        await mark_debt_as_paid(unpaid_debt.id, db_session)
        await db_session.refresh(unpaid_debt)

        assert unpaid_debt.is_paid is True


class TestGetDebtById:
    async def test_returns_debt_when_exists(
        self,
        db_session: AsyncSession,
        game_with_debts: tuple[Game, list[Debt]],
    ):
        game, debts = game_with_debts

        result = await get_debt_by_id(debts[0].id, db_session)

        assert result is not None
        assert result.id == debts[0].id

    async def test_returns_none_when_not_exists(self, db_session: AsyncSession):
        result = await get_debt_by_id(99999, db_session)

        assert result is None


class TestGetUnpaidDebtsAsDebtor:
    async def test_returns_unpaid_debts_where_user_is_debtor(
        self,
        db_session: AsyncSession,
        game_with_debts: tuple[Game, list[Debt]],
        multiple_users: list[User],
    ):
        game, debts = game_with_debts
        # debts[0] is unpaid (is_paid=False), debtor is multiple_users[1]

        result = await get_unpaid_debts_as_debtor(multiple_users[1].id, db_session)

        assert len(result) == 1
        assert result[0].debtor_id == multiple_users[1].id

    async def test_returns_empty_when_all_paid(
        self,
        db_session: AsyncSession,
        finished_game: Game,
        multiple_users: list[User],
    ):
        from datetime import datetime, UTC

        debt = Debt(
            game_id=finished_game.id,
            creditor_id=multiple_users[0].id,
            debtor_id=multiple_users[1].id,
            amount=500,
            is_paid=True,
            paid_at=datetime.now(UTC),
        )
        db_session.add(debt)
        await db_session.flush()

        result = await get_unpaid_debts_as_debtor(multiple_users[1].id, db_session)

        assert result == []

    async def test_returns_debt_when_is_paid_but_no_paid_at(
        self,
        db_session: AsyncSession,
        finished_game: Game,
        multiple_users: list[User],
    ):
        debt = Debt(
            game_id=finished_game.id,
            creditor_id=multiple_users[0].id,
            debtor_id=multiple_users[1].id,
            amount=500,
            is_paid=True,
            paid_at=None,  # Not fully paid
        )
        db_session.add(debt)
        await db_session.flush()

        result = await get_unpaid_debts_as_debtor(multiple_users[1].id, db_session)

        assert len(result) == 1


class TestGetUnpaidDebtsAsCreditor:
    async def test_returns_unpaid_debts_where_user_is_creditor(
        self,
        db_session: AsyncSession,
        game_with_debts: tuple[Game, list[Debt]],
        multiple_users: list[User],
    ):
        game, debts = game_with_debts
        # debts[0] is unpaid (is_paid=False), creditor is multiple_users[0]

        result = await get_unpaid_debts_as_creditor(multiple_users[0].id, db_session)

        assert len(result) == 1
        assert result[0].creditor_id == multiple_users[0].id

    async def test_returns_empty_when_no_debts(
        self, db_session: AsyncSession, multiple_users: list[User]
    ):
        result = await get_unpaid_debts_as_creditor(multiple_users[3].id, db_session)

        assert result == []
