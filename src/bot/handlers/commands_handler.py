from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import Settings
from bot.controllers.debt import (
    calculate_debt_amount,
    get_unpaid_debts_as_creditor,
    get_unpaid_debts_as_debtor,
)
from bot.controllers.game import (
    games_hosting_count,
    games_playing_count,
    get_active_game,
    get_mvp_count,
    get_player_total_buy_in,
    get_player_total_buy_out,
)
from bot.controllers.record import get_record
from bot.internal.admin_menu import build_admin_menu
from bot.internal.context import SettingsForm
from bot.internal.keyboards import debt_stats_kb, game_menu_kb
from bot.internal.lexicon import ORDER, SETTINGS_QUESTIONS, texts
from database.models import User

router = Router()


@router.message(CommandStart(), F.chat.type == "private")
async def command_handler(
    message: Message,
    user: User,
) -> None:
    await message.answer(
        text=texts["start_greeting"].format(user.fullname),
    )


@router.message(Command("admin"), F.chat.type == "private")
async def admin_command(
    message: Message,
    user: User,
    db_session: AsyncSession,
    state: FSMContext,
) -> None:
    if not user.is_admin:
        await message.answer(text=texts["insufficient_privileges"])
        return
    text, status = await build_admin_menu(db_session)
    await message.answer(
        text=text, reply_markup=game_menu_kb(status=status, is_admin=user.is_admin)
    )


@router.message(Command("settings"), F.chat.type == "private")
async def settings_start(
    message: Message,
    state: FSMContext,
    user: User,
):
    await state.clear()
    user.IBAN = None
    user.bank = None
    user.name_surname = None
    first_field = ORDER[0]
    await state.set_state(getattr(SettingsForm, first_field))
    question = SETTINGS_QUESTIONS[first_field]
    await message.answer(question)


@router.message(Command("info"), F.chat.type == "private")
async def info_command(message: Message, settings: Settings) -> None:
    await message.answer(text=texts["info_message"].format(settings.bot.ADMIN_IBAN, settings.bot.ADMIN_NAME))


@router.message(Command("stats"), F.chat.type == "private")
async def stats_command(message: Message, user: User, db_session: AsyncSession):
    games_hosted = await games_hosting_count(user.id, db_session)
    games_played = await games_playing_count(user.id, db_session)
    mvp_count = await get_mvp_count(user.id, db_session)
    total_buy_in = await get_player_total_buy_in(user.id, db_session) or 0
    total_buy_out = await get_player_total_buy_out(user.id, db_session) or 0
    total_net = total_buy_out - total_buy_in
    if total_buy_in > 0:
        total_roi_value = (total_net / total_buy_in) * 100
        total_roi_str = f"{total_roi_value:.2f}%"
    else:
        total_roi_str = "0%" if total_buy_out == 0 else "∞%"

    active_game = await get_active_game(db_session)
    record = None
    if active_game:
        record = await get_record(active_game.id, user.id, db_session)

    if active_game and record:
        current_buy_in = record.buy_in or 0
        stats_text = texts["player_stats_ingame"].format(
            active_game.id,
            current_buy_in,
            games_played,
            games_hosted,
            mvp_count,
            total_buy_in,
            total_buy_out,
            total_roi_str,
        )
    else:
        stats_text = texts["player_stats_outgame"].format(
            games_played,
            games_hosted,
            mvp_count,
            total_buy_in,
            total_buy_out,
            total_roi_str,
        )

    # Build debts section (aggregated by player)
    debts_as_debtor = await get_unpaid_debts_as_debtor(user.id, db_session)
    debts_as_creditor = await get_unpaid_debts_as_creditor(user.id, db_session)

    reply_markup = None
    if debts_as_debtor or debts_as_creditor:
        debts_text = texts["stats_debts_header"]

        if debts_as_debtor:
            debts_text += texts["stats_debts_you_owe"]
            # Aggregate by creditor
            creditor_totals: dict[int, tuple[str, float]] = {}
            for debt in debts_as_debtor:
                amount = float(calculate_debt_amount(debt.amount, debt.game.ratio))
                creditor_id = debt.creditor_id
                if creditor_id in creditor_totals:
                    name, total = creditor_totals[creditor_id]
                    creditor_totals[creditor_id] = (name, total + amount)
                else:
                    creditor_totals[creditor_id] = (debt.creditor.fullname, amount)
            for name, total in creditor_totals.values():
                debts_text += texts["stats_debt_aggregated"].format(name, total)

        if debts_as_creditor:
            debts_text += texts["stats_debts_owed_to_you"]
            # Aggregate by debtor
            debtor_totals: dict[int, tuple[str, float]] = {}
            for debt in debts_as_creditor:
                amount = float(calculate_debt_amount(debt.amount, debt.game.ratio))
                debtor_id = debt.debtor_id
                if debtor_id in debtor_totals:
                    name, total = debtor_totals[debtor_id]
                    debtor_totals[debtor_id] = (name, total + amount)
                else:
                    debtor_totals[debtor_id] = (debt.debtor.fullname, amount)
            for name, total in debtor_totals.values():
                debts_text += texts["stats_debt_aggregated"].format(name, total)

        stats_text += debts_text
        reply_markup = debt_stats_kb(
            has_debts_i_owe=bool(debts_as_debtor),
            has_debts_owe_me=bool(debts_as_creditor),
        )

    await message.answer(text=stats_text, reply_markup=reply_markup)
