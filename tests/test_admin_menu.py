from sqlalchemy.ext.asyncio import AsyncSession

from bot.internal.admin_menu import build_admin_menu
from bot.internal.context import GameStatus
from database.models import Game, Record


class TestBuildAdminMenu:
    async def test_returns_idle_state_when_no_active_game(
        self, db_session: AsyncSession
    ):
        text, status = await build_admin_menu(db_session)

        assert status is None
        assert "Status: <b>Idle</b>" in text
        assert "Select an action below." in text

    async def test_uses_live_buy_in_sum_and_lists_players(
        self,
        db_session: AsyncSession,
        game_with_records: tuple[Game, list[Record]],
    ):
        text, status = await build_admin_menu(db_session)

        assert status == GameStatus.ACTIVE
        assert "Game: <b>01</b>" in text
        assert "Host: <b>Player Two</b>" in text
        assert "Players: <b>3</b>" in text
        assert "Total pot: <b>6000</b>" in text
        assert "Current players and BUY-IN:" in text
        assert "Player One: <b>1000</b>" in text
        assert "Player Two: <b>2000</b>" in text
        assert "Player Three: <b>3000</b>" in text
