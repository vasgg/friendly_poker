import asyncio
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from aiogram.exceptions import TelegramNetworkError, TelegramRetryAfter

from bot.internal import poll


@pytest.mark.parametrize(
    ("now", "expected"),
    [
        ("2026-09-11T12:59:00+04:00", "2026-09-11T13:00:00+04:00"),
        ("2026-09-11T13:00:00+04:00", "2026-09-18T13:00:00+04:00"),
        ("2026-09-11T13:18:00+04:00", "2026-09-18T13:00:00+04:00"),
        ("2026-09-10T23:00:00+00:00", "2026-09-11T13:00:00+04:00"),
    ],
)
def test_next_friday(now, expected):
    assert poll._next_friday_13(datetime.fromisoformat(now)) == datetime.fromisoformat(expected)


@pytest.mark.parametrize("rate_limited", [False, True])
async def test_failed_send_retries_same_occurrence(monkeypatch, tmp_path, rate_limited):
    current = datetime(2026, 9, 11, 12, 59, tzinfo=poll.TZ)

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return current

    delays = []

    async def sleep(seconds):
        nonlocal current
        delays.append(seconds)
        if len(delays) == 3:
            raise asyncio.CancelledError
        current += timedelta(seconds=seconds)

    failure = (
        TelegramRetryAfter(method=Mock(), message="Flood control", retry_after=37)
        if rate_limited
        else TelegramNetworkError(method=Mock(), message="Request timeout")
    )
    bot = SimpleNamespace(
        send_poll=AsyncMock(side_effect=[failure, SimpleNamespace(message_id=123)]),
        pin_chat_message=AsyncMock(),
    )
    monkeypatch.setattr(poll, "datetime", Clock)
    monkeypatch.setattr(poll, "sleep", sleep)
    monkeypatch.setattr(poll, "_PINS_FILE", tmp_path / "pins.json")

    with pytest.raises(asyncio.CancelledError):
        await poll.weekly_poll_loop(bot, -1001)

    retry = 37 if rate_limited else 5
    assert delays == [60, retry, 7 * 86400 - retry]
    assert bot.send_poll.await_count == 2
    bot.pin_chat_message.assert_awaited_once()
    assert await poll._load_last_pinned_poll_id(-1001) == 123


async def test_pin_failure_does_not_resend_poll(monkeypatch, tmp_path):
    bot = SimpleNamespace(
        send_poll=AsyncMock(return_value=SimpleNamespace(message_id=123)),
        pin_chat_message=AsyncMock(side_effect=RuntimeError("Pin failed")),
    )
    monkeypatch.setattr(poll, "_PINS_FILE", tmp_path / "pins.json")
    monkeypatch.setattr(poll, "sleep", AsyncMock(side_effect=[None, asyncio.CancelledError]))

    with pytest.raises(asyncio.CancelledError):
        await poll.weekly_poll_loop(bot, -1001)

    bot.send_poll.assert_awaited_once()
    bot.pin_chat_message.assert_awaited_once()


@pytest.mark.parametrize("phase", ["waiting", "sending", "retrying"])
async def test_loop_cancellation_stops_requests(monkeypatch, phase):
    reached = asyncio.Event()
    bot = SimpleNamespace(send_poll=AsyncMock())

    async def block(*args, **kwargs):
        reached.set()
        await asyncio.Future()

    if phase == "waiting":
        monkeypatch.setattr(poll, "sleep", block)
    elif phase == "sending":
        monkeypatch.setattr(poll, "sleep", AsyncMock())
        bot.send_poll.side_effect = block
    else:
        bot.send_poll.side_effect = RuntimeError("Send failed")

        async def sleep(seconds):
            if seconds == 5:
                await block()

        monkeypatch.setattr(poll, "sleep", sleep)

    task = poll.start_weekly_poll_loop(bot, -1001)
    try:
        await asyncio.wait_for(reached.wait(), timeout=1)
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    assert bot.send_poll.await_count == (0 if phase == "waiting" else 1)


@pytest.mark.parametrize("startup_fails", [False, True])
async def test_main_stops_poll_before_closing_session(monkeypatch, startup_fails):
    for name, value in {
        "BOT_TOKEN": "test-token",
        "BOT_ADMIN": "1",
        "BOT_ADMIN_IBAN": "TESTIBAN",
        "BOT_ADMIN_NAME": "Test Admin",
        "BOT_GROUP_ID": "-1001",
        "DB_URL": "postgresql+asyncpg://user:pass@localhost:5432/test_db",
    }.items():
        monkeypatch.setenv(name, value)

    from bot import main

    events = []
    started = asyncio.Event()

    async def background():
        try:
            started.set()
            await asyncio.Future()
        finally:
            events.append("poll stopped")

    async def close_session():
        events.append("session closed")

    async def start_polling(bot, *, close_bot_session):
        assert close_bot_session is False
        await asyncio.wait_for(started.wait(), timeout=1)
        if startup_fails:
            raise RuntimeError("Startup failed")

    bot = SimpleNamespace(session=SimpleNamespace(close=AsyncMock(side_effect=close_session)))
    dispatcher = Mock(start_polling=AsyncMock(side_effect=start_polling))
    monkeypatch.setattr(main, "initial_setup", Mock())
    monkeypatch.setattr(main, "Bot", Mock(return_value=bot))
    monkeypatch.setattr(main, "Dispatcher", Mock(return_value=dispatcher))
    monkeypatch.setattr(main, "get_db", Mock())
    monkeypatch.setattr(
        main, "start_weekly_poll_loop", lambda *args: asyncio.create_task(background())
    )

    if startup_fails:
        with pytest.raises(RuntimeError, match="Startup failed"):
            await main.main()
    else:
        await main.main()

    assert events == ["poll stopped", "session closed"]


@pytest.mark.parametrize("fails", [False, True])
def test_run_main_drains_logging_after_event_loop(monkeypatch, fails):
    from bot import main

    events = []

    async def fake_main():
        events.append("main")
        if fails:
            raise RuntimeError("Failed")

    listeners = [Mock(), Mock()]
    listeners[0].stop.side_effect = lambda: events.append("file stopped")
    listeners[1].stop.side_effect = lambda: events.append("console stopped")
    monkeypatch.setattr(main, "initial_setup", Mock(return_value=listeners))
    monkeypatch.setattr(main, "main", fake_main)

    if fails:
        with pytest.raises(RuntimeError, match="Failed"):
            main.run_main()
    else:
        main.run_main()

    assert events == ["main", "file stopped", "console stopped"]
