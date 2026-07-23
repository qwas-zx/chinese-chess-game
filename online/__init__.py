"""
Online (multiplayer) module package.

Components:
- message:           Unified message structure + validation
- connection_registry: sid -> {user_id, username, room_id} binding
- room_manager:      Room state machine (seq, history, dedup, snapshot)
"""
from .message import (
    build_message, validate_message_structure, MESSAGE_TYPES,
    build_ack, build_state_update, build_game_start, build_error
)
from .connection_registry import connection_registry
from .room_manager import room_manager

__all__ = [
    'build_message', 'validate_message_structure', 'MESSAGE_TYPES',
    'build_ack', 'build_state_update', 'build_game_start', 'build_error',
    'connection_registry', 'room_manager',
]
