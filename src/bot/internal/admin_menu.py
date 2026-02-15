import html

from sqlalchemy.ext.asyncio import AsyncSession

from bot.controllers.game import get_active_game
from bot.controllers.user import get_user_from_db_by_tg_id
from bot.internal.context import GameStatus
from bot.internal.lexicon import texts


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

    host = await get_user_from_db_by_tg_id(game.host_id, db_session)
    host_name = host.fullname if host else "Unknown"
    text = "\n".join(
        [
            texts["admin_menu_header"],
            texts["admin_menu_status_active"],
            texts["admin_menu_game_line"].format(game.id),
            texts["admin_menu_host_line"].format(html.escape(host_name)),
            texts["admin_menu_players_line"].format(len(game.records)),
            texts["admin_menu_total_pot_line"].format(game.total_pot or 0),
            "",
            texts["admin_menu_hint"],
        ]
    )
    return text, GameStatus.ACTIVE
