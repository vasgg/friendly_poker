import os
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

os.environ.setdefault("BOT_TOKEN", "test-token")
os.environ.setdefault("BOT_ADMIN", "1")
os.environ.setdefault("BOT_ADMIN_IBAN", "TESTIBAN")
os.environ.setdefault("BOT_ADMIN_NAME", "Test Admin")
os.environ.setdefault("BOT_GROUP_ID", "-1001")
os.environ.setdefault("DB_URL", "postgresql+asyncpg://user:pass@localhost:5432/test_db")

from bot.handlers import commands_handler


async def _return_zero(*args, **kwargs) -> int:
    return 0


async def _return_empty_list(*args, **kwargs) -> list:
    return []


@pytest.mark.parametrize(
    ("player_id", "current_buy_in"),
    [
        (1, 1000),
        (2, 2500),
        (3, 7000),
    ],
)
async def test_stats_shows_current_buy_in_for_each_player_in_active_game(
    monkeypatch: pytest.MonkeyPatch,
    player_id: int,
    current_buy_in: int,
):
    active_game = SimpleNamespace(id=7)
    user = SimpleNamespace(id=player_id)
    message = AsyncMock()

    async def fake_get_active_game(db_session):
        return active_game

    async def fake_get_record(game_id, requested_user_id, db_session):
        assert game_id == active_game.id
        assert requested_user_id == player_id
        return SimpleNamespace(buy_in=current_buy_in)

    monkeypatch.setattr(commands_handler, "games_hosting_count", _return_zero)
    monkeypatch.setattr(commands_handler, "games_playing_count", _return_zero)
    monkeypatch.setattr(commands_handler, "get_mvp_count", _return_zero)
    monkeypatch.setattr(commands_handler, "get_player_total_buy_in", _return_zero)
    monkeypatch.setattr(commands_handler, "get_player_total_buy_out", _return_zero)
    monkeypatch.setattr(commands_handler, "get_active_game", fake_get_active_game)
    monkeypatch.setattr(commands_handler, "get_record", fake_get_record)
    monkeypatch.setattr(
        commands_handler, "get_unpaid_debts_as_creditor", _return_empty_list
    )
    monkeypatch.setattr(
        commands_handler, "get_unpaid_debts_as_debtor", _return_empty_list
    )

    await commands_handler.stats_command(message=message, user=user, db_session=object())

    message.answer.assert_awaited_once()
    answer_text = message.answer.await_args.kwargs["text"]
    assert "Game <b>07</b> in progress." in answer_text
    assert f"Current BUY-IN: <b>{current_buy_in}</b>" in answer_text
