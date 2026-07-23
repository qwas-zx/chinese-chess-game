"""
Routes Package

- register_routes:        local two-player game (per-user session)
- register_ai_routes:     single-player vs AI battle (per-user session)
- register_auth_routes:   registration / login / logout / me
- register_room_routes:   online room control plane (HTTP)
- register_ws_handlers:   online data plane (SocketIO)
"""
from .game_routes import register_routes
from .ai_routes import register_ai_routes
from .auth_routes import register_auth_routes
from .room_routes import register_room_routes
from .ws_routes import register_ws_handlers

__all__ = [
    'register_routes', 'register_ai_routes', 'register_auth_routes',
    'register_room_routes', 'register_ws_handlers',
]
