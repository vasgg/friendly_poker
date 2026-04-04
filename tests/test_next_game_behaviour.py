import logging
import os
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from aiogram.exceptions import TelegramBadRequest

os.environ.setdefault("BOT_TOKEN", "test-token")
os.environ.setdefault("BOT_ADMIN", "1")
os.environ.setdefault("BOT_ADMIN_IBAN", "TESTIBAN")
os.environ.setdefault("BOT_ADMIN_NAME", "Test Admin")
os.environ.setdefault("BOT_GROUP_ID", "-1001")
os.environ.setdefault("DB_URL", "postgresql+asyncpg://user:pass@localhost:5432/test_db")

from bot.controllers.game import (
    consume_next_game_settings_for_new_game,
    get_next_game_settings,
    update_next_game_ratio,
    update_next_game_yearly_stats,
)
from bot.handlers import photo_handler, states_handler
from bot.handlers.callbacks import common, finalization, multiselect, next_game_settings
from bot.internal.context import FinalGameAction, KeyboardMode
from bot.services import game_finalization, photo_reminder


class FakeState:
    def __init__(self, data: dict | None = None):
        self.data = dict(data or {})
        self.current_state = None

    async def get_data(self) -> dict:
        return dict(self.data)

    async def update_data(self, **kwargs) -> None:
        self.data.update(kwargs)

    async def set_state(self, state=None) -> None:
        self.current_state = state


def _telegram_bad_request(message: str) -> TelegramBadRequest:
    return TelegramBadRequest(method=Mock(), message=message)


async def test_next_game_settings_singleton_defaults(db_session):
    settings = await get_next_game_settings(db_session)

    assert settings.ratio == 1
    assert settings.yearly_stats is False
    assert settings.version == 1


async def test_next_game_ratio_update_rejects_stale_version(db_session):
    first_update = await update_next_game_ratio(
        ratio=3,
        expected_version=1,
        admin_id=77,
        admin_name="Boss Admin",
        db_session=db_session,
    )
    stale_update = await update_next_game_ratio(
        ratio=4,
        expected_version=1,
        admin_id=88,
        admin_name="Other Admin",
        db_session=db_session,
    )
    current = await get_next_game_settings(db_session)

    assert first_update is not None
    assert first_update.ratio == 3
    assert first_update.version == 2
    assert stale_update is None
    assert current.ratio == 3
    assert current.yearly_stats is False
    assert current.version == 2


async def test_next_game_settings_are_consumed_by_one_new_game(
    db_session,
    multiple_users,
):
    ratio_update = await update_next_game_ratio(
        ratio=4,
        expected_version=1,
        admin_id=multiple_users[0].id,
        admin_name=multiple_users[0].fullname,
        db_session=db_session,
    )
    assert ratio_update is not None

    yearly_update = await update_next_game_yearly_stats(
        enabled=True,
        expected_version=ratio_update.version,
        admin_id=multiple_users[0].id,
        admin_name=multiple_users[0].fullname,
        db_session=db_session,
    )
    assert yearly_update is not None

    game, consumed = await consume_next_game_settings_for_new_game(
        admin_id=multiple_users[0].id,
        host_id=multiple_users[1].id,
        db_session=db_session,
    )
    current = await get_next_game_settings(db_session)

    assert game is not None
    assert consumed.ratio == 4
    assert consumed.yearly_stats is True
    assert game.ratio == 4
    assert game.send_yearly_stats_on_finish is True
    assert current.ratio == 1
    assert current.yearly_stats is False
    assert current.version == yearly_update.version + 1


async def test_next_game_ratio_confirm_logs_admin_and_ratio(monkeypatch, caplog):
    callback = SimpleNamespace(
        answer=AsyncMock(),
        message=AsyncMock(),
        bot=SimpleNamespace(send_message=AsyncMock()),
        from_user=SimpleNamespace(id=77, username="boss"),
    )
    user = SimpleNamespace(is_admin=True, fullname="Boss Admin")
    callback_data = SimpleNamespace(confirm=True, ratio=3, version=5)
    edit_or_answer = AsyncMock()

    async def fake_update_next_game_ratio(**kwargs):
        assert kwargs["ratio"] == 3
        assert kwargs["expected_version"] == 5
        assert kwargs["admin_id"] == 77
        return SimpleNamespace(version=6)

    monkeypatch.setattr(next_game_settings, "_edit_or_answer", edit_or_answer)
    monkeypatch.setattr(next_game_settings, "update_next_game_ratio", fake_update_next_game_ratio)
    caplog.set_level(logging.INFO, logger=next_game_settings.logger.name)

    await next_game_settings.next_game_ratio_confirm_handler(
        callback=callback,
        callback_data=callback_data,
        user=user,
        db_session=object(),
    )

    assert "Next game ratio confirmed: admin_id=77 username=boss ratio=3 version=6" in caplog.text
    callback.bot.send_message.assert_awaited_once_with(
        chat_id=next_game_settings.settings.bot.GROUP_ID,
        text=next_game_settings.texts["ratio_set_group"].format(
            ratio=3,
            admin_name="Boss Admin",
        ),
    )
    edit_or_answer.assert_awaited_once()


async def test_next_game_yearly_stats_confirm_can_disable(monkeypatch):
    callback = SimpleNamespace(
        answer=AsyncMock(),
        message=AsyncMock(),
        from_user=SimpleNamespace(id=77, username="boss"),
    )
    user = SimpleNamespace(is_admin=True, fullname="Boss Admin")
    callback_data = SimpleNamespace(confirm=False, version=8)
    edit_or_answer = AsyncMock()

    async def fake_update_next_game_yearly_stats(**kwargs):
        assert kwargs["enabled"] is False
        assert kwargs["expected_version"] == 8
        return SimpleNamespace(version=9)

    monkeypatch.setattr(next_game_settings, "_edit_or_answer", edit_or_answer)
    monkeypatch.setattr(
        next_game_settings,
        "update_next_game_yearly_stats",
        fake_update_next_game_yearly_stats,
    )

    await next_game_settings.next_game_yearly_stats_confirm_handler(
        callback=callback,
        callback_data=callback_data,
        user=user,
        db_session=object(),
    )

    assert (
        edit_or_answer.await_args.kwargs["text"] == next_game_settings.texts["yearly_stats_unset"]
    )


async def test_multiselect_new_game_uses_shared_settings_snapshot(monkeypatch):
    users = [
        SimpleNamespace(id=10, fullname="Host One", games_played=0, last_time_played=False),
        SimpleNamespace(id=11, fullname="Host Two", games_played=0, last_time_played=False),
        SimpleNamespace(id=12, fullname="Player", games_played=0, last_time_played=False),
    ]

    async def fake_get_bot_id(bot):
        return bot.id

    async def fake_get_all_users(db_session):
        return users

    async def fake_consume_next_game_settings_for_new_game(**kwargs):
        return (
            SimpleNamespace(
                id=100,
                created_at=datetime.now(UTC),
                message_id=None,
            ),
            SimpleNamespace(ratio=2, yearly_stats=True),
        )

    async def fake_create_record(game_id, user_id, db_session, flush=False):
        return SimpleNamespace(game_id=game_id, user_id=user_id)

    monkeypatch.setattr(multiselect, "_get_bot_id", fake_get_bot_id)
    monkeypatch.setattr(multiselect, "get_all_users", fake_get_all_users)
    monkeypatch.setattr(
        multiselect,
        "consume_next_game_settings_for_new_game",
        fake_consume_next_game_settings_for_new_game,
    )
    monkeypatch.setattr(multiselect, "create_record", fake_create_record)
    monkeypatch.setattr(multiselect, "schedule_photo_reminder", lambda **kwargs: None)

    state = FakeState(
        {
            "next_game_host_id": 10,
            "chosen_for_new_game": [10, 12],
        }
    )
    callback = SimpleNamespace(
        answer=AsyncMock(),
        bot=SimpleNamespace(
            id=999,
            send_message=AsyncMock(return_value=SimpleNamespace(message_id=321)),
        ),
        message=AsyncMock(),
        from_user=SimpleNamespace(id=1, username="admin"),
    )
    user = SimpleNamespace(is_admin=True, fullname="Admin Boss")
    callback_data = SimpleNamespace(mode=KeyboardMode.NEW_GAME, game_id=0)
    db_session = SimpleNamespace(add=Mock(), flush=AsyncMock())

    await multiselect.multiselect_further_handler(
        callback=callback,
        callback_data=callback_data,
        user=user,
        state=state,
        db_session=db_session,
    )

    group_message = callback.bot.send_message.await_args.kwargs["text"]
    assert "Admin: <b>Admin Boss</b>." in group_message
    assert "Ratio: <b>x2</b>." in group_message
    assert "next_game_ratio" not in state.data
    assert state.data["next_game_host_id"] is None
    assert state.data["chosen_for_new_game"] == []


async def test_send_yearly_stats_if_enabled_uses_game_flag(monkeypatch):
    bot = SimpleNamespace(send_message=AsyncMock())
    created_at = datetime(2026, 4, 4, 18, 0, tzinfo=UTC).replace(tzinfo=None)

    async def fake_get_game_by_id(game_id, db_session):
        return SimpleNamespace(
            id=game_id,
            created_at=created_at,
            send_yearly_stats_on_finish=True,
        )

    async def fake_get_yearly_stats(year, db_session):
        assert year == 2026
        return object(), object()

    monkeypatch.setattr(game_finalization, "get_game_by_id", fake_get_game_by_id)
    monkeypatch.setattr(game_finalization, "get_yearly_stats", fake_get_yearly_stats)
    monkeypatch.setattr(
        game_finalization,
        "generate_yearly_stats_report",
        lambda year, summary, players: f"report:{year}",
    )

    await game_finalization.send_yearly_stats_if_enabled(bot, 7, object())

    bot.send_message.assert_awaited_once_with(
        chat_id=game_finalization.settings.bot.GROUP_ID,
        text="report:2026",
    )


async def test_edit_or_answer_ignores_message_not_modified():
    message = SimpleNamespace(
        edit_text=AsyncMock(
            side_effect=_telegram_bad_request(
                "Bad Request: message is not modified: specified new message content and reply markup are exactly the same as a current content and reply markup of the message"
            )
        ),
        answer=AsyncMock(),
    )

    await common._edit_or_answer(message, "same text")

    message.answer.assert_not_awaited()


async def test_edit_reply_markup_or_answer_ignores_message_not_modified():
    message = SimpleNamespace(
        edit_reply_markup=AsyncMock(
            side_effect=_telegram_bad_request(
                "Bad Request: message is not modified: specified new message content and reply markup are exactly the same as a current content and reply markup of the message"
            )
        ),
        answer=AsyncMock(),
    )

    await common._edit_reply_markup_or_answer(message, reply_markup=object(), text="fallback")

    message.answer.assert_not_awaited()


async def test_abort_game_handler_rejects_stale_callback(monkeypatch):
    callback = SimpleNamespace(
        answer=AsyncMock(),
        message=AsyncMock(),
        from_user=SimpleNamespace(id=77),
        bot=object(),
    )
    user = SimpleNamespace(is_admin=True)
    callback_data = SimpleNamespace(game_id=7)
    hard_abort_game = AsyncMock()

    monkeypatch.setattr(finalization, "get_active_game", AsyncMock(return_value=None))
    monkeypatch.setattr(finalization, "hard_abort_game", hard_abort_game)

    await finalization.abort_game_handler(
        callback=callback,
        callback_data=callback_data,
        user=user,
        db_session=object(),
    )

    callback.message.answer.assert_awaited_once_with(
        text=finalization.texts["game_no_longer_active"].format(7)
    )
    hard_abort_game.assert_not_awaited()


async def test_finish_game_handler_rejects_stale_callback(monkeypatch):
    callback = SimpleNamespace(
        answer=AsyncMock(),
        message=AsyncMock(),
        from_user=SimpleNamespace(id=77),
        bot=SimpleNamespace(id=999),
    )
    user = SimpleNamespace(is_admin=True)
    callback_data = SimpleNamespace(
        game_id=7,
        action=FinalGameAction.FINALIZE_GAME,
    )
    do_finalize = AsyncMock()

    monkeypatch.setattr(
        finalization,
        "get_active_game",
        AsyncMock(return_value=SimpleNamespace(id=8)),
    )
    monkeypatch.setattr(finalization, "_do_finalize", do_finalize)

    await finalization.finish_game_handler(
        callback=callback,
        callback_data=callback_data,
        user=user,
        db_session=object(),
    )

    callback.message.answer.assert_awaited_once_with(
        text=finalization.texts["game_no_longer_active"].format(7)
    )
    do_finalize.assert_not_awaited()


async def test_multiselect_further_rejects_stale_add_players_callback(monkeypatch):
    state = FakeState({"chosen_for_add_players": [10, 11]})
    callback = SimpleNamespace(
        answer=AsyncMock(),
        message=AsyncMock(),
        from_user=SimpleNamespace(id=77),
        bot=SimpleNamespace(id=999),
    )
    user = SimpleNamespace(is_admin=True)
    callback_data = SimpleNamespace(mode=KeyboardMode.ADD_PLAYERS, game_id=7)
    create_record = AsyncMock()

    monkeypatch.setattr(multiselect, "_get_bot_id", AsyncMock(return_value=999))
    monkeypatch.setattr(multiselect, "get_all_users", AsyncMock(return_value=[]))
    monkeypatch.setattr(
        multiselect,
        "get_active_game",
        AsyncMock(return_value=SimpleNamespace(id=8)),
    )
    monkeypatch.setattr(multiselect, "create_record", create_record)

    await multiselect.multiselect_further_handler(
        callback=callback,
        callback_data=callback_data,
        user=user,
        state=state,
        db_session=SimpleNamespace(),
    )

    callback.message.answer.assert_awaited_once_with(
        text=multiselect.texts["game_no_longer_active"].format(7)
    )
    create_record.assert_not_awaited()


async def test_enter_buy_out_rejects_stale_state(monkeypatch):
    state = FakeState({"player_id": 10, "game_id": 7})
    message = AsyncMock()
    message.text = "1000"

    monkeypatch.setattr(states_handler, "get_active_game", AsyncMock(return_value=None))
    monkeypatch.setattr(states_handler, "update_record", AsyncMock())

    await states_handler.enter_buy_out(
        message=message,
        state=state,
        db_session=object(),
    )

    message.answer.assert_awaited_once_with(
        text=states_handler.texts["game_no_longer_active"].format(7)
    )
    assert state.data["player_id"] is None
    assert state.data["game_id"] is None
    assert state.current_state is None
    states_handler.update_record.assert_not_awaited()


async def test_clear_photo_warning_uses_original_chat_id():
    bot = SimpleNamespace(delete_message=AsyncMock())

    photo_reminder.set_photo_warning(game_id=7, chat_id=12345, message_id=678)

    await photo_reminder.clear_photo_warning(bot, 7)

    bot.delete_message.assert_awaited_once_with(chat_id=12345, message_id=678)


async def test_photo_reminder_text_mentions_admin_and_reply_requirement(monkeypatch):
    sent_messages = []

    async def fake_sleep(_seconds):
        return None

    async def fake_send_message(**kwargs):
        sent_messages.append(kwargs)
        return SimpleNamespace(message_id=321)

    monkeypatch.setattr(photo_reminder.asyncio, "sleep", fake_sleep)

    bot = SimpleNamespace(send_message=fake_send_message)
    info = photo_reminder.ReminderInfo(
        game_id=7,
        admin_id=11,
        admin_username="boss",
        host_fullname="Host",
        game_created_at=datetime.now(UTC),
    )

    await photo_reminder._reminder_task(bot, info)

    assert sent_messages[0]["chat_id"] == photo_reminder.settings.bot.GROUP_ID
    assert "@boss" in sent_messages[0]["text"]
    assert "Any player can save the photo" in sent_messages[0]["text"]
    assert "replying to this message" in sent_messages[0]["text"]


async def test_handle_photo_reply_allows_any_player_reply(monkeypatch):
    uploader_id = 555
    callback_bot = SimpleNamespace(send_message=AsyncMock())
    message = SimpleNamespace(
        reply_to_message=SimpleNamespace(message_id=999),
        from_user=SimpleNamespace(id=uploader_id, full_name="Uploader"),
        photo=[SimpleNamespace(file_id="photo-1")],
        document=None,
        bot=callback_bot,
    )
    game = SimpleNamespace(photo_name=None, photo_id=None)
    db_session = SimpleNamespace(flush=AsyncMock())

    monkeypatch.setattr(
        photo_handler,
        "get_reminder_info",
        lambda _message_id: photo_reminder.ReminderInfo(
            game_id=7,
            admin_id=11,
            admin_username="boss",
            host_fullname="Host",
            game_created_at=datetime.now(UTC),
        ),
    )
    monkeypatch.setattr(
        photo_handler,
        "save_game_photo",
        AsyncMock(return_value="/tmp/game7_photo.jpg"),
    )
    monkeypatch.setattr(
        photo_handler,
        "get_game_by_id",
        AsyncMock(return_value=game),
    )
    monkeypatch.setattr(
        photo_handler,
        "get_record",
        AsyncMock(return_value=SimpleNamespace(user_id=uploader_id)),
    )
    monkeypatch.setattr(photo_handler, "clear_photo_warning", AsyncMock())
    cancel_photo_reminder = Mock()
    monkeypatch.setattr(photo_handler, "cancel_photo_reminder", cancel_photo_reminder)

    await photo_handler.handle_photo_reply(message=message, db_session=db_session)

    assert game.photo_name == "game7_photo.jpg"
    assert game.photo_id == "photo-1"
    cancel_photo_reminder.assert_called_once_with(7)
    sent_notifications = {
        (call.kwargs["chat_id"], call.kwargs["text"])
        for call in callback_bot.send_message.await_args_list
    }
    assert (
        uploader_id,
        "Game 7. Photo saved: /tmp/game7_photo.jpg",
    ) in sent_notifications
    assert (
        11,
        "Game 7. Photo saved by Uploader: /tmp/game7_photo.jpg",
    ) in sent_notifications


async def test_handle_photo_reply_ignores_non_player(monkeypatch):
    callback_bot = SimpleNamespace(send_message=AsyncMock())
    message = SimpleNamespace(
        reply_to_message=SimpleNamespace(message_id=999),
        from_user=SimpleNamespace(id=777, full_name="Spectator"),
        photo=[SimpleNamespace(file_id="photo-1")],
        document=None,
        bot=callback_bot,
        answer=AsyncMock(),
    )

    monkeypatch.setattr(
        photo_handler,
        "get_reminder_info",
        lambda _message_id: photo_reminder.ReminderInfo(
            game_id=7,
            admin_id=11,
            admin_username="boss",
            host_fullname="Host",
            game_created_at=datetime.now(UTC),
        ),
    )
    monkeypatch.setattr(photo_handler, "get_record", AsyncMock(return_value=None))
    save_game_photo = AsyncMock()
    monkeypatch.setattr(photo_handler, "save_game_photo", save_game_photo)

    await photo_handler.handle_photo_reply(message=message, db_session=object())

    save_game_photo.assert_not_awaited()
    message.answer.assert_awaited_once_with(
        photo_handler.texts["photo_upload_forbidden"].format(game_id=7)
    )
    callback_bot.send_message.assert_not_awaited()


async def test_schedule_photo_reminder_registers_start_message(monkeypatch):
    created_tasks = []

    def fake_create_task(coro):
        created_tasks.append(coro)
        coro.close()
        return SimpleNamespace(cancel=Mock())

    monkeypatch.setattr(photo_reminder.asyncio, "create_task", fake_create_task)

    photo_reminder.schedule_photo_reminder(
        bot=object(),
        game_id=7,
        admin_id=11,
        admin_username="boss",
        host_fullname="Host",
        game_created_at=datetime.now(UTC),
        source_message_id=321,
    )

    assert photo_reminder.get_reminder_info(321) is not None
    photo_reminder.cancel_photo_reminder(7)


async def test_handle_photo_reply_notifies_admin_on_failure(monkeypatch):
    uploader_id = 555
    callback_bot = SimpleNamespace(send_message=AsyncMock())
    message = SimpleNamespace(
        reply_to_message=SimpleNamespace(message_id=999),
        from_user=SimpleNamespace(id=uploader_id, full_name="Uploader"),
        photo=[SimpleNamespace(file_id="photo-1")],
        document=None,
        bot=callback_bot,
    )

    monkeypatch.setattr(
        photo_handler,
        "get_reminder_info",
        lambda _message_id: photo_reminder.ReminderInfo(
            game_id=7,
            admin_id=11,
            admin_username="boss",
            host_fullname="Host",
            game_created_at=datetime.now(UTC),
        ),
    )
    monkeypatch.setattr(
        photo_handler,
        "save_game_photo",
        AsyncMock(side_effect=RuntimeError("disk failed")),
    )
    monkeypatch.setattr(
        photo_handler,
        "get_record",
        AsyncMock(return_value=SimpleNamespace(user_id=uploader_id)),
    )

    await photo_handler.handle_photo_reply(message=message, db_session=object())

    sent_notifications = {
        (call.kwargs["chat_id"], call.kwargs["text"])
        for call in callback_bot.send_message.await_args_list
    }
    assert (
        11,
        "Game 7. Photo save failed for Uploader (555). Error: RuntimeError: disk failed",
    ) in sent_notifications
    assert (
        uploader_id,
        "Game 7. Failed to save photo. The admin has been notified.",
    ) in sent_notifications
