import math

from aiogram.exceptions import TelegramBadRequest

from database.models import User

MAX_INLINE_BUTTONS = 100
PAGINATED_PAGE_SIZE = 98


def _paginate_players(players: list[User], page: int) -> tuple[list[User], int, int]:
    total = len(players)
    if total <= MAX_INLINE_BUTTONS:
        return players, 1, 0
    total_pages = max(1, math.ceil(total / PAGINATED_PAGE_SIZE))
    page = max(0, min(page, total_pages - 1))
    start = page * PAGINATED_PAGE_SIZE
    end = start + PAGINATED_PAGE_SIZE
    return players[start:end], total_pages, page


async def _edit_or_answer(message, text: str, reply_markup=None) -> None:
    try:
        await message.edit_text(text=text, reply_markup=reply_markup)
    except TelegramBadRequest:
        await message.answer(text=text, reply_markup=reply_markup)


async def _get_bot_id(bot) -> int:
    bot_id = getattr(bot, "id", None)
    if bot_id:
        return bot_id
    cached = getattr(bot, "_cached_id", None)
    if cached:
        return cached
    me = await bot.get_me()
    bot._cached_id = me.id
    return me.id


def _filter_users(users: list[User], exclude_ids: set[int]) -> list[User]:
    return [user for user in users if user.id not in exclude_ids]


def _filter_ids(values: list[int], exclude_id: int) -> list[int]:
    return [value for value in values if value != exclude_id]

