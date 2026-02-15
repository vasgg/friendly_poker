import html
import logging
from decimal import Decimal

from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession

from bot.controllers.debt import calculate_debt_amount, get_debts_with_users
from bot.controllers.game import get_game_by_id
from bot.internal.keyboards import get_paid_button
from bot.internal.lexicon import texts
from bot.internal.notify_admin import send_message_to_player
from database.models import Debt, User

logger = logging.getLogger(__name__)


def format_username(user: User) -> str:
    label = f"@{user.username}" if user.username else user.fullname
    return html.escape(label)


def format_debtor_message(
    debt: Debt,
    amount: Decimal,
    creditor_username: str,
    creditor: User,
) -> str:
    """Format the debtor notification message with or without requisites."""
    has_requisites = all((creditor.bank, creditor.IBAN, creditor.name_surname))

    if has_requisites:
        bank = html.escape(creditor.bank or "")
        iban = html.escape(creditor.IBAN or "")
        name = html.escape(creditor.name_surname or "")
        return texts["debtor_personal_game_report_with_requisites"].format(
            debt.game_id,
            debt.id,
            amount,
            creditor_username,
            bank,
            iban,
            name,
        )
    return texts["debtor_personal_game_report"].format(
        debt.game_id, debt.id, amount, creditor_username
    )


def format_creditor_message(
    debt: Debt,
    amount: Decimal,
    debtor_username: str,
) -> str:
    return texts["creditor_personal_game_report"].format(
        debt.game_id, debt.id, debtor_username, amount
    )


async def send_debtor_notification(
    bot: Bot,
    debt: Debt,
    debtor: User,
    amount: Decimal,
    creditor_username: str,
    creditor: User,
    db_session: AsyncSession,
) -> bool:
    debtor_text = format_debtor_message(debt, amount, creditor_username, creditor)

    msg = await send_message_to_player(
        bot,
        user_id=debtor.id,
        fullname=debtor.fullname,
        text=debtor_text,
        reply_markup=await get_paid_button(debt.id, debtor.id),
    )

    if msg:
        debt.debt_message_id = msg.message_id
        await db_session.flush()
        logger.info(
            "Debt notification sent to debtor %s for debt %s",
            debtor.id,
            debt.id,
        )
        return True
    return False


async def send_creditor_notification(
    bot: Bot,
    debt: Debt,
    creditor: User,
    amount: Decimal,
    debtor_username: str,
) -> None:
    creditor_text = format_creditor_message(debt, amount, debtor_username)

    await send_message_to_player(
        bot,
        user_id=creditor.id,
        fullname=creditor.fullname,
        text=creditor_text,
    )
    logger.info(
        "Debt notification sent to creditor %s for debt %s",
        creditor.id,
        debt.id,
    )


async def notify_all_debts(
    game_id: int,
    bot: Bot,
    db_session: AsyncSession,
) -> None:
    """
    Send debt notifications to all debtors and creditors for a game.

    This function:
    1. Fetches the game and all debts with users eagerly loaded
    2. For each debt, sends notification to debtor (with payment button)
    3. For each debt, sends notification to creditor
    4. Saves message IDs to database for later reference
    """
    game = await get_game_by_id(game_id, db_session)
    if game is None:
        logger.error("Game %s not found for debt notification", game_id)
        return

    debts = await get_debts_with_users(game_id, db_session)
    logger.info("Sending notifications for %d debts in game %s", len(debts), game_id)

    for debt in debts:
        creditor = debt.creditor
        debtor = debt.debtor

        creditor_username = format_username(creditor)
        debtor_username = format_username(debtor)
        amount = calculate_debt_amount(debt.amount, game.ratio)

        try:
            await send_debtor_notification(
                bot=bot,
                debt=debt,
                debtor=debtor,
                amount=amount,
                creditor_username=creditor_username,
                creditor=creditor,
                db_session=db_session,
            )
        except Exception:
            logger.exception(
                "Failed to notify debtor %s for debt %s", debtor.id, debt.id
            )

        try:
            await send_creditor_notification(
                bot=bot,
                debt=debt,
                creditor=creditor,
                amount=amount,
                debtor_username=debtor_username,
            )
        except Exception:
            logger.exception(
                "Failed to notify creditor %s for debt %s", creditor.id, debt.id
            )

    logger.info("All debt notifications sent for game %s", game_id)
