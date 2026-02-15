from aiogram import Router

from bot.handlers.callbacks.add_funds import router as add_funds_router
from bot.handlers.callbacks.delete_player import router as delete_player_router
from bot.handlers.callbacks.finalization import router as finalization_router
from bot.handlers.callbacks.game_menu import router as game_menu_router
from bot.handlers.callbacks.multiselect import router as multiselect_router
from bot.handlers.callbacks.next_game_settings import router as next_game_settings_router
from bot.handlers.callbacks.single_player_actions import router as single_player_actions_router

router = Router()
router.include_router(game_menu_router)
router.include_router(single_player_actions_router)
router.include_router(multiselect_router)
router.include_router(next_game_settings_router)
router.include_router(add_funds_router)
router.include_router(delete_player_router)
router.include_router(finalization_router)

__all__ = ["router"]
