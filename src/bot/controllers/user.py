import logging

from sqlalchemy import Result, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import settings
from bot.internal.lexicon import ORDER, SETTINGS_QUESTIONS
from database.models import Record, User

logger = logging.getLogger(__name__)


async def add_user_to_db(user, db_session: AsyncSession) -> User:
    is_admin = True if user.id == settings.bot.ADMIN else False
    new_user = User(
        id=user.id, fullname=user.full_name, username=user.username, is_admin=is_admin
    )
    db_session.add(new_user)
    await db_session.commit()
    logger.info(f"New user created: {new_user}")
    return new_user


async def get_user_from_db_by_tg_id(
    telegram_id: int, db_session: AsyncSession
) -> User | None:
    query = select(User).filter(User.id == telegram_id)
    result: Result = await db_session.execute(query)
    user = result.unique().scalar_one_or_none()
    return user


async def get_all_users(db_session: AsyncSession) -> list[User]:
    query = select(User)
    result: Result = await db_session.execute(query)
    return list(result.unique().scalars().all())


async def get_last_played_users(db_session: AsyncSession) -> list[User.id]:
    query = select(User.id).where(User.last_time_played)
    result: Result = await db_session.execute(query)
    return list(result.unique().scalars().all())


async def get_players_from_game(game_id: int, db_session: AsyncSession) -> list[User]:
    query = (
        select(User)
        .join(Record, User.id == Record.user_id)
        .where(Record.game_id == game_id)
    )
    result = await db_session.execute(query)
    return list(result.unique().scalars().all())


async def get_unplayed_users(db_session: AsyncSession) -> list[User]:
    query = select(User).where(~User.last_time_played)
    result: Result = await db_session.execute(query)
    return list(result.unique().scalars().all())


async def get_users_with_buyout(game_id: int, db_session: AsyncSession) -> list[User]:
    query = (
        select(User)
        .join(Record, User.id == Record.user_id)
        .where(Record.game_id == game_id, Record.buy_out.isnot(0))
    )
    result = await db_session.execute(query)
    return list(result.unique().scalars().all())


async def ask_next_question(user: User) -> tuple:
    for field in ORDER:
        if getattr(user, field) is None:
            question = SETTINGS_QUESTIONS[field]
            return field, question
    return None, None
