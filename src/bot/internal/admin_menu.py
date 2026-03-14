import html

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from bot.controllers.game import get_active_game
from bot.controllers.user import get_user_from_db_by_tg_id
from bot.internal.context import GameStatus
from bot.internal.lexicon import texts
from database.models import Record


async def build_admin_menu(db_session: AsyncSession) -> tuple[str, GameStatus | None]:
    game = await get_active_game(db_session)
    if not game:
        text = "\n".join(
            [
                texts["admin_menu_header"],
                texts["admin_menu_status_idle"],
                "",
                texts["admin_menu_hint"],
            ]
        )
        return text, None

    records_query = (
        select(Record)
        .where(Record.game_id == game.id)
        .options(selectinload(Record.user))
        .order_by(Record.id.asc())
    )
    records_result = await db_session.execute(records_query)
    records = records_result.unique().scalars().all()
    total_pot = sum(record.buy_in or 0 for record in records)
    players_buy_in_lines = [
        texts["admin_menu_player_buy_in_line"].format(
            html.escape(record.user.fullname if record.user else "Unknown"),
            record.buy_in or 0,
        )
        for record in records
    ]
    if not players_buy_in_lines:
        players_buy_in_lines = [texts["admin_menu_player_buy_in_empty"]]

    host = await get_user_from_db_by_tg_id(game.host_id, db_session)
    host_name = host.fullname if host else "Unknown"
    text = "\n".join(
        [
            texts["admin_menu_header"],
            texts["admin_menu_status_active"],
            texts["admin_menu_game_line"].format(game.id),
            texts["admin_menu_host_line"].format(html.escape(host_name)),
            texts["admin_menu_players_line"].format(len(records)),
            texts["admin_menu_total_pot_line"].format(total_pot),
            texts["admin_menu_player_buy_ins_header"],
            *players_buy_in_lines,
            "",
            texts["admin_menu_hint"],
        ]
    )
    return text, GameStatus.ACTIVE
