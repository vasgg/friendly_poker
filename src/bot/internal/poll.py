from asyncio import create_task, sleep
from datetime import datetime, timedelta, time
import logging
from zoneinfo import ZoneInfo
from aiogram import Bot

logger = logging.getLogger(__name__)
TZ = ZoneInfo("Asia/Tbilisi")


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
    await bot.send_poll(
        chat_id=group_id,
        question="Weekly Texas No Limit Hold'em.\nEntrance: 21:00",
        options=["Go, I'll host", "Go", "Go, I have a +1", "No way"],
        is_anonymous=False,
        allows_multiple_answers=False,
    )


async def weekly_poll_loop(bot: Bot, group_id: int) -> None:
    while True:
        try:
            now = datetime.now(TZ)
            target = _next_friday_13(now)
            sleep_s = (target - now).total_seconds()
            logger.info(
                "Next weekly poll at %s (in %s)",
                target.strftime("%Y-%m-%d %H:%M:%S %Z"),
                _fmt_delta(target - now),
            )
            await sleep(sleep_s)
            await _send_poll(bot, group_id)
        except Exception:
            logger.exception("weekly_poll_loop error")
            await sleep(5)


def start_weekly_poll_loop(bot: Bot, group_id: int):
    now = datetime.now(TZ)
    target = _next_friday_13(now)
    logger.info(
        "Weekly poll scheduled for %s (in %s)",
        target.strftime("%Y-%m-%d %H:%M:%S %Z"),
        _fmt_delta(target - now),
    )
    return create_task(weekly_poll_loop(bot, group_id))
