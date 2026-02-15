import logging
from dataclasses import dataclass
from datetime import UTC

from aiogram import Bot
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import settings
from bot.controllers.debt import flush_debts_to_db
from bot.controllers.game import (
    commit_game_results_to_db,
    generate_yearly_stats_report,
    get_game_by_id,
    get_group_game_report,
    get_yearly_stats,
)
from bot.controllers.record import (
    check_game_balance,
    debt_calculator,
    get_mvp,
    get_roi_from_game_by_player_id,
    update_net_profit_and_roi,
)
from bot.controllers.user import get_user_from_db_by_tg_id
from bot.internal.lexicon import texts
from bot.internal.poll import unpin_current_poll
from bot.internal.schemas import GameBalanceData
from bot.services.debt_notification import notify_all_debts
from bot.services.photo_reminder import cancel_photo_reminder

logger = logging.getLogger(__name__)


@dataclass
class FinalizationResult:
    success: bool
    error_message: str | None = None


async def validate_game_balance(
    results: GameBalanceData,
) -> FinalizationResult:
    if results.total_pot is None or results.delta is None:
        return FinalizationResult(
            success=False,
            error_message=texts["check_game_balance_error"],
        )

    if results.delta > 0:
        return FinalizationResult(
            success=False,
            error_message=texts["exit_game_wrong_total_sum>0"].format(
                results.total_pot, results.delta
            ),
        )

    if results.delta < 0:
        return FinalizationResult(
            success=False,
            error_message=texts["exit_game_wrong_total_sum<0"].format(
                results.total_pot, abs(results.delta)
            ),
        )

    return FinalizationResult(success=True)


async def calculate_and_save_debts(
    game_id: int,
    db_session: AsyncSession,
) -> None:
    await update_net_profit_and_roi(game_id, db_session)
    transactions = await debt_calculator(game_id, db_session)
    await flush_debts_to_db(transactions, db_session)
    logger.info("Debts calculated and saved for game %s", game_id)


async def determine_mvp(
    game_id: int,
    db_session: AsyncSession,
) -> tuple[int | None, str | None, float | None]:
    mvp_id = await get_mvp(game_id, db_session)
    if mvp_id is None:
        logger.warning("No MVP found for game %s", game_id)
        return None, None, None

    mvp_player = await get_user_from_db_by_tg_id(mvp_id, db_session)
    if mvp_player is None:
        logger.warning("MVP player not found in DB: user_id=%s", mvp_id)
        return None, None, None

    mvp_roi = await get_roi_from_game_by_player_id(game_id, mvp_id, db_session)
    return mvp_id, mvp_player.fullname, mvp_roi


async def send_game_report_to_group(
    bot: Bot,
    game_id: int,
    mvp_fullname: str,
    mvp_roi: float,
    db_session: AsyncSession,
) -> None:
    """Generate and send game report to the group chat."""
    text = await get_group_game_report(game_id, mvp_fullname, mvp_roi, db_session)
    await bot.send_message(chat_id=settings.bot.GROUP_ID, text=text)
    logger.info("Game %s report sent to group", game_id)


async def send_yearly_stats_if_enabled(
    bot: Bot,
    game_id: int,
    state: FSMContext,
    db_session: AsyncSession,
) -> None:
    """Send yearly stats to group if enabled in state."""
    data = await state.get_data()
    if not data.get("next_game_yearly_stats"):
        return

    game = await get_game_by_id(game_id, db_session)
    if game is None:
        logger.warning("Game %s not found for yearly stats", game_id)
        return

    created_at = game.created_at
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=UTC)

    year = created_at.astimezone(settings.bot.TIMEZONE).year
    summary, players = await get_yearly_stats(year, db_session)
    yearly_text = generate_yearly_stats_report(year, summary, players)

    await bot.send_message(chat_id=settings.bot.GROUP_ID, text=yearly_text)
    await state.update_data(next_game_yearly_stats=False)
    logger.info("Yearly stats for %s sent to group", year)


async def finalize_game(
    game_id: int,
    bot: Bot,
    state: FSMContext,
    db_session: AsyncSession,
) -> FinalizationResult:
    logger.info("Starting finalization of game %s", game_id)
    cancel_photo_reminder(game_id)

    # Step 1: Validate balance
    results = await check_game_balance(game_id, db_session)
    validation = await validate_game_balance(results)
    if not validation.success:
        return validation

    # Step 2: Calculate and save debts
    await calculate_and_save_debts(game_id, db_session)

    # Step 3: Determine MVP
    mvp_id, mvp_fullname, mvp_roi = await determine_mvp(game_id, db_session)
    if mvp_id is None:
        return FinalizationResult(
            success=False,
            error_message=texts["mvp_not_found"],
        )

    # Step 4: Commit game results to DB
    assert results.total_pot is not None
    await commit_game_results_to_db(game_id, results.total_pot, mvp_id, db_session)
    await db_session.commit()

    # Step 5: Send debt notifications
    try:
        await notify_all_debts(game_id, bot, db_session)
    except Exception:
        logger.exception("Game %s: debt notifications failed", game_id)
    finally:
        await db_session.commit()

    # Step 6: Send group report
    try:
        assert mvp_fullname is not None
        assert mvp_roi is not None
        await send_game_report_to_group(bot, game_id, mvp_fullname, mvp_roi, db_session)
    except Exception:
        logger.exception("Game %s: failed to send group report", game_id)

    # Step 7: Send yearly stats if enabled
    try:
        await send_yearly_stats_if_enabled(bot, game_id, state, db_session)
    except Exception:
        logger.exception("Game %s: failed to send yearly stats", game_id)

    # Step 8: Unpin the weekly poll
    try:
        await unpin_current_poll(bot, settings.bot.GROUP_ID)
    except Exception:
        logger.exception("Game %s: failed to unpin poll", game_id)

    logger.info("Game %s finalized successfully", game_id)
    return FinalizationResult(success=True)
