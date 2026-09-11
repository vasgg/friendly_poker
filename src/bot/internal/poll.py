import json
import logging
from asyncio import Task, create_task, sleep
from datetime import datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import aiofiles
import aiofiles.os
from aiogram import Bot
from aiogram.exceptions import TelegramRetryAfter

logger = logging.getLogger(__name__)
TZ = ZoneInfo("Asia/Tbilisi")

_PINS_FILE = Path(__file__).resolve().parent / "poll_pins.json"


async def _load_last_pinned_poll_id(group_id: int) -> int | None:
    try:
        if await aiofiles.os.path.exists(_PINS_FILE):
            async with aiofiles.open(_PINS_FILE, encoding="utf-8") as f:
                content = await f.read()
                data = json.loads(content)
                val = data.get(str(group_id))
                return int(val) if val is not None else None
    except Exception:
        logger.exception("Failed to load last pinned poll id for chat %s", group_id)
    return None


async def _save_last_pinned_poll_id(group_id: int, message_id: int | None) -> None:
    try:
        data = {}
        if await aiofiles.os.path.exists(_PINS_FILE):
            try:
                async with aiofiles.open(_PINS_FILE, encoding="utf-8") as f:
                    content = await f.read()
                    data = json.loads(content)
            except Exception:
                logger.warning("Pins file corrupted, recreating")
                data = {}
        if message_id is None:
            data.pop(str(group_id), None)
        else:
            data[str(group_id)] = message_id
        async with aiofiles.open(_PINS_FILE, mode="w", encoding="utf-8") as f:
            await f.write(json.dumps(data, ensure_ascii=False))
    except Exception:
        logger.exception("Failed to save last pinned poll id for chat %s", group_id)


async def unpin_current_poll(bot: Bot, group_id: int) -> None:
    try:
        message_id = await _load_last_pinned_poll_id(group_id)
        if message_id is None:
            logger.debug("No pinned poll to unpin for chat %s", group_id)
            return

        await bot.unpin_chat_message(chat_id=group_id, message_id=message_id)
        await _save_last_pinned_poll_id(group_id, None)
        logger.info(
            "Unpinned poll message %s in chat %s after game finalization", message_id, group_id
        )
    except Exception:
        logger.exception("Failed to unpin poll in chat %s", group_id)


def _next_friday_13(now: datetime) -> datetime:
    now = now.astimezone(TZ)
    target_t = time(hour=13, tzinfo=TZ)
    days_ahead = (4 - now.weekday()) % 7
    candidate = datetime.combine(now.date() + timedelta(days=days_ahead), target_t)
    if candidate <= now:
        candidate += timedelta(days=7)
    return candidate


def _fmt_delta(td: timedelta) -> str:
    total = int(td.total_seconds())
    days, rem = divmod(total, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, seconds = divmod(rem, 60)
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if not parts:
        parts.append(f"{seconds}s")
    return " ".join(parts)


async def _send_poll(bot: Bot, group_id: int) -> None:
    logger.info("Sending weekly poll to chat %s", group_id)
    msg = await bot.send_poll(
        chat_id=group_id,
        question="Weekly Texas No Limit Hold'em.\nEntrance: 20:00",
        options=["Go, I'll host", "Go, I have a +1", "Go", "No way"],
        is_anonymous=False,
        allows_multiple_answers=False,
    )
    logger.info("Sent weekly poll message %s to chat %s", msg.message_id, group_id)
    try:
        prev_id = await _load_last_pinned_poll_id(group_id)
        if prev_id is not None:
            try:
                await bot.unpin_chat_message(chat_id=group_id, message_id=prev_id)
                logger.info(
                    "Unpinned previous weekly poll message %s in chat %s",
                    prev_id,
                    group_id,
                )
            except Exception:
                logger.warning("Could not unpin previous poll %s in chat %s", prev_id, group_id)

        await bot.pin_chat_message(
            chat_id=group_id,
            message_id=msg.message_id,
            disable_notification=False,
        )
        logger.info("Pinned weekly poll message %s in chat %s", msg.message_id, group_id)
        await _save_last_pinned_poll_id(group_id, msg.message_id)
    except Exception:
        logger.exception("Failed to pin poll message in chat %s", group_id)


async def weekly_poll_loop(bot: Bot, group_id: int) -> None:
    while True:
        now = datetime.now(TZ)
        target = _next_friday_13(now)
        logger.info(
            "Next weekly poll at %s (in %s)",
            target.strftime("%Y-%m-%d %H:%M:%S %Z"),
            _fmt_delta(target - now),
        )
        await sleep((target - now).total_seconds())
        retry_delay = 5
        # Keep this occurrence pending after a failure instead of scheduling next week.
        while True:
            try:
                await _send_poll(bot, group_id)
                break
            except TelegramRetryAfter as exc:
                delay = exc.retry_after
                logger.warning("Weekly poll rate limited; retrying in %s seconds", delay)
            except Exception:
                delay = retry_delay
                logger.exception("Weekly poll failed; retrying in %s seconds", delay)
            await sleep(delay)
            retry_delay = min(retry_delay * 2, 300)


def start_weekly_poll_loop(bot: Bot, group_id: int) -> Task[None]:
    now = datetime.now(TZ)
    target = _next_friday_13(now)
    logger.info(
        "Weekly poll scheduled for %s (in %s)",
        target.strftime("%Y-%m-%d %H:%M:%S %Z"),
        _fmt_delta(target - now),
    )
    return create_task(weekly_poll_loop(bot, group_id))
