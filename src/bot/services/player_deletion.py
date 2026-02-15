import html
import logging
from dataclasses import dataclass
from datetime import UTC

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from bot.config import settings
from bot.controllers.debt import calculate_debt_amount
from bot.controllers.record import get_mvp, update_net_profit_and_roi
from bot.internal.lexicon import texts
from database.models import Debt, Game, Record, User

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class DeletePlayerDbResult:
    player_id: int
    player_name: str
    debts_removed: int
    records_removed: int
    host_reassigned_games: list[int]
    mvp_recalculated_games: list[int]
    pot_recalculated_games: list[int]
    counterparty_lines: dict[int, list[str]]
    counterparty_names: dict[int, str]
    admin_summary_text: str


def _format_game_date(created_at) -> str:
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=UTC)
    return created_at.astimezone(settings.bot.TIMEZONE).strftime("%d.%m.%Y")


def _format_debt_lines(debts: list[Debt], direction: str) -> list[str]:
    lines: list[str] = []
    for debt in debts:
        amount = calculate_debt_amount(debt.amount, debt.game.ratio)
        amount_str = f"{amount:.2f}"
        game_date = _format_game_date(debt.game.created_at)
        if direction == "owes":
            counterparty = html.escape(debt.creditor.fullname)
            lines.append(
                f"• Game {debt.game_id:02d} ({game_date}): "
                f"<b>{amount_str} GEL</b> → {counterparty}"
            )
        else:
            counterparty = html.escape(debt.debtor.fullname)
            lines.append(
                f"• Game {debt.game_id:02d} ({game_date}): "
                f"<b>{amount_str} GEL</b> ← {counterparty}"
            )
    return lines


def build_delete_summary(
    player: User,
    debts_as_debtor: list[Debt],
    debts_as_creditor: list[Debt],
) -> tuple[str, bool]:
    lines = [
        texts["admin_delete_player_summary_header"].format(html.escape(player.fullname))
    ]
    has_debts = bool(debts_as_debtor or debts_as_creditor)
    lines.append("")
    if not has_debts:
        lines.append(texts["admin_delete_player_summary_no_debts"])
        return "\n".join(lines), False
    lines.append(texts["admin_delete_player_summary_debts_header"])
    if debts_as_debtor:
        lines.append(texts["admin_delete_player_summary_owes"])
        lines.extend(_format_debt_lines(debts_as_debtor, "owes"))
    if debts_as_creditor:
        lines.append(texts["admin_delete_player_summary_owed"])
        lines.extend(_format_debt_lines(debts_as_creditor, "owed"))
    return "\n".join(lines), True


def player_in_active_game(active_game: Game | None, player_id: int) -> bool:
    if not active_game:
        return False
    if active_game.host_id == player_id:
        return True
    return any(record.user_id == player_id for record in active_game.records)


def _is_unpaid(debt: Debt) -> bool:
    return (debt.is_paid is False) or (debt.paid_at is None)


def _collect_counterparty_lines(player: User, debts: list[Debt]) -> dict[int, list[str]]:
    counterparty_lines: dict[int, list[str]] = {}
    for debt in debts:
        amount = calculate_debt_amount(debt.amount, debt.game.ratio)
        amount_str = f"{amount:.2f}"
        game_date = _format_game_date(debt.game.created_at)
        if debt.debtor_id == player.id:
            recipient_id = debt.creditor_id
            line = (
                f"• Game {debt.game_id:02d} ({game_date}): "
                f"<b>{amount_str} GEL</b> — "
                f"{html.escape(player.fullname)} owed you."
            )
        else:
            recipient_id = debt.debtor_id
            line = (
                f"• Game {debt.game_id:02d} ({game_date}): "
                f"<b>{amount_str} GEL</b> — "
                f"you owed {html.escape(player.fullname)}."
            )
        counterparty_lines.setdefault(recipient_id, []).append(line)
    return counterparty_lines


async def _calculate_total_pot(game_id: int, db_session: AsyncSession) -> int:
    total_query = select(func.coalesce(func.sum(Record.buy_in), 0)).where(
        Record.game_id == game_id
    )
    result = await db_session.execute(total_query)
    return result.scalar_one()


async def delete_player_from_db(
    player: User,
    admin_id: int,
    db_session: AsyncSession,
) -> DeletePlayerDbResult:
    player_name = player.fullname
    player_id = player.id

    debts_query = (
        select(Debt)
        .where((Debt.debtor_id == player_id) | (Debt.creditor_id == player_id))
        .options(
            selectinload(Debt.creditor),
            selectinload(Debt.debtor),
            selectinload(Debt.game),
        )
    )
    debts_result = await db_session.execute(debts_query)
    debts_all = list(debts_result.unique().scalars().all())
    debts_unpaid = [debt for debt in debts_all if _is_unpaid(debt)]
    debts_unpaid_as_debtor = [debt for debt in debts_unpaid if debt.debtor_id == player_id]
    debts_unpaid_as_creditor = [
        debt for debt in debts_unpaid if debt.creditor_id == player_id
    ]
    counterparty_lines = _collect_counterparty_lines(player, debts_unpaid)
    counterparty_names: dict[int, str] = {}
    for debt in debts_unpaid:
        if debt.creditor:
            counterparty_names[debt.creditor_id] = debt.creditor.fullname
        if debt.debtor:
            counterparty_names[debt.debtor_id] = debt.debtor.fullname

    admin_summary_text, _ = build_delete_summary(
        player,
        debts_unpaid_as_debtor,
        debts_unpaid_as_creditor,
    )

    for debt in debts_all:
        amount = calculate_debt_amount(debt.amount, debt.game.ratio)
        logger.info(
            "Delete player debt removed: admin_id=%s user_id=%s debt_id=%s game_id=%s "
            "debtor_id=%s creditor_id=%s amount=%s paid=%s",
            admin_id,
            player_id,
            debt.id,
            debt.game_id,
            debt.debtor_id,
            debt.creditor_id,
            f"{amount:.2f}",
            debt.is_paid,
        )

    records_count_result = await db_session.execute(
        select(func.count()).select_from(Record).where(Record.user_id == player_id)
    )
    records_count = records_count_result.scalar_one()

    record_games_result = await db_session.execute(
        select(Record.game_id).where(Record.user_id == player_id)
    )
    record_game_ids = sorted(set(record_games_result.scalars().all()))

    host_games_result = await db_session.execute(
        select(Game.id).where(Game.host_id == player_id)
    )
    host_game_ids = list(host_games_result.scalars().all())

    mvp_games_result = await db_session.execute(
        select(Game.id).where(Game.mvp_id == player_id)
    )
    mvp_game_ids = list(mvp_games_result.scalars().all())

    await db_session.execute(
        delete(Debt).where((Debt.debtor_id == player_id) | (Debt.creditor_id == player_id))
    )
    await db_session.execute(delete(Record).where(Record.user_id == player_id))

    if host_game_ids:
        await db_session.execute(
            update(Game).where(Game.host_id == player_id).values(host_id=Game.admin_id)
        )

    recalc_game_ids = sorted(set(record_game_ids) | set(mvp_game_ids))
    for game_id in recalc_game_ids:
        await update_net_profit_and_roi(game_id, db_session)
        total_pot = await _calculate_total_pot(game_id, db_session)
        await db_session.execute(
            update(Game).where(Game.id == game_id).values(total_pot=total_pot)
        )

    for game_id in mvp_game_ids:
        new_mvp_id = await get_mvp(game_id, db_session)
        await db_session.execute(
            update(Game).where(Game.id == game_id).values(mvp_id=new_mvp_id)
        )
        logger.info(
            "Delete player MVP recalculated: admin_id=%s game_id=%s old_mvp=%s new_mvp=%s",
            admin_id,
            game_id,
            player_id,
            new_mvp_id,
        )

    await db_session.delete(player)
    await db_session.flush()

    logger.info(
        "Player deleted: admin_id=%s user_id=%s debts_removed=%s records_removed=%s "
        "host_reassigned_games=%s total_pot_recalc_games=%s",
        admin_id,
        player_id,
        len(debts_all),
        records_count,
        host_game_ids,
        recalc_game_ids,
    )

    return DeletePlayerDbResult(
        player_id=player_id,
        player_name=player_name,
        debts_removed=len(debts_all),
        records_removed=records_count,
        host_reassigned_games=host_game_ids,
        mvp_recalculated_games=mvp_game_ids,
        pot_recalculated_games=recalc_game_ids,
        counterparty_lines=counterparty_lines,
        counterparty_names=counterparty_names,
        admin_summary_text=admin_summary_text,
    )

