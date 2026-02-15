from aiogram.enums import ButtonStyle
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.internal.callbacks import DebtActionCbData, DebtStatsCbData
from bot.internal.context import DebtAction, DebtStatsView
from bot.internal.lexicon import buttons


async def get_paid_button(debt_id: int, chat_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="DEBT PAID",
                    callback_data=DebtActionCbData(
                        action=DebtAction.MARK_AS_PAID,
                        debt_id=debt_id,
                        chat_id=chat_id,
                    ).pack(),
                    style=ButtonStyle.SUCCESS,
                )
            ],
        ]
    )


async def get_paid_button_confirmation(debt_id: int, chat_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="confirm payment",
                    callback_data=DebtActionCbData(
                        action=DebtAction.COMPLETE_DEBT,
                        debt_id=debt_id,
                        chat_id=chat_id,
                    ).pack(),
                    style=ButtonStyle.SUCCESS,
                )
            ],
        ],
    )


def debt_details_i_owe_kb(debts, user_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for debt in debts:
        builder.button(
            text=buttons["debt_detail_paid"].format(debt.game_id, debt.creditor.fullname),
            callback_data=DebtActionCbData(
                action=DebtAction.MARK_AS_PAID,
                debt_id=debt.id,
                chat_id=user_id,
            ).pack(),
            style=ButtonStyle.SUCCESS,
        )
    builder.adjust(1)
    return builder.as_markup()


def debt_details_owe_me_kb(debts, user_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for debt in debts:
        builder.button(
            text=buttons["debt_detail_remind"].format(debt.game_id, debt.debtor.fullname),
            callback_data=DebtActionCbData(
                action=DebtAction.REMIND_DEBTOR,
                debt_id=debt.id,
                chat_id=user_id,
            ).pack(),
            style=ButtonStyle.PRIMARY,
        )
    builder.adjust(1)
    return builder.as_markup()


def debt_stats_kb(has_debts_i_owe: bool, has_debts_owe_me: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if has_debts_i_owe:
        builder.button(
            text=buttons["debt_stats_i_owe"],
            callback_data=DebtStatsCbData(view=DebtStatsView.I_OWE).pack(),
            style=ButtonStyle.DANGER,
        )
    if has_debts_owe_me:
        builder.button(
            text=buttons["debt_stats_owe_me"],
            callback_data=DebtStatsCbData(view=DebtStatsView.OWE_ME).pack(),
            style=ButtonStyle.SUCCESS,
        )
    builder.adjust(2)
    return builder.as_markup()

