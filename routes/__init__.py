"""
Routes Package

- register_routes:           local two-player game (per-user session)
- register_ai_routes:        single-player vs AI battle (per-user session)
- register_auth_routes:      registration / login / logout / me
- register_room_routes:      online room control plane (HTTP)
- register_ws_handlers:       online data plane (SocketIO)
- register_leaderboard_routes: public leaderboard page + API
- register_admin_routes:     admin management page + API (admin only)
"""
from .game_routes import register_routes
from .ai_routes import register_ai_routes
from .auth_routes import register_auth_routes
from .room_routes import register_room_routes
from .ws_routes import register_ws_handlers
from .leaderboard_routes import register_leaderboard_routes
from .admin_routes import register_admin_routes

__all__ = [
    'register_routes', 'register_ai_routes', 'register_auth_routes',
    'register_room_routes', 'register_ws_handlers',
    'register_leaderboard_routes', 'register_admin_routes',
]
