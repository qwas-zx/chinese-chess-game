"""
Per-user Game Session Manager

Local two-player games and AI battles used to share one global ChessGame
instance, so every visitor saw the same board state ("as soon as I open
the page I'm on the previous player's position"). This module fixes that
by keeping one game instance per authenticated user.

Storage is an in-memory dict keyed by ``user_id``. A simple time-based
eviction cleans up sessions that haven't been touched in a while so idle
users don't leak memory.
"""
import time
from copy import deepcopy

from .core import ChessGame
from .ai import ChessAI


# Sessions untouched for longer than this are evicted on the next cleanup.
SESSION_TTL_SECONDS = 60 * 60  # 1 hour

# Cleanup runs at most once every this many get_or_create calls.
CLEANUP_INTERVAL_CALLS = 100


class GameSessionManager:
    """Manage one ChessGame (+ optional ChessAI) per user."""

    def __init__(self):
        # user_id -> { 'game': ChessGame, 'ai': ChessAI or None, 'last_touch': float }
        self._sessions = {}
        self._call_counter = 0

    # ---------- public API ----------

    def get_local_game(self, user_id):
        """Return the user's local two-player game, creating one if needed."""
        sess = self._get_or_create(user_id)
        return sess['game']

    def get_ai_game(self, user_id):
        """Return (ChessGame, ChessAI) for the user, creating on first access."""
        sess = self._get_or_create(user_id)
        if sess['ai'] is None:
            sess['ai'] = ChessAI(color='black', difficulty='normal')
        return sess['game_ai'], sess['ai']

    def reset_local_game(self, user_id):
        sess = self._get_or_create(user_id)
        sess['game'].reset()
        return sess['game']

    def reset_ai_game(self, user_id, difficulty=None):
        sess = self._get_or_create(user_id)
        if sess['ai'] is None:
            sess['ai'] = ChessAI(color='black', difficulty=difficulty or 'normal')
        elif difficulty:
            sess['ai'].set_difficulty(difficulty)
        sess['game_ai'].reset()
        return sess['game_ai'], sess['ai']

    def remove(self, user_id):
        self._sessions.pop(user_id, None)

    def touch(self, user_id):
        if user_id in self._sessions:
            self._sessions[user_id]['last_touch'] = time.time()

    # ---------- internals ----------

    def _get_or_create(self, user_id):
        self._call_counter += 1
        if self._call_counter % CLEANUP_INTERVAL_CALLS == 0:
            self._cleanup()

        if user_id not in self._sessions:
            self._sessions[user_id] = {
                'game': ChessGame(),        # local two-player
                'game_ai': ChessGame(),     # AI battle (separate instance)
                'ai': None,                 # lazy-init ChessAI
                'last_touch': time.time(),
            }
        else:
            self._sessions[user_id]['last_touch'] = time.time()
        return self._sessions[user_id]

    def _cleanup(self):
        now = time.time()
        expired = [uid for uid, s in self._sessions.items()
                   if now - s['last_touch'] > SESSION_TTL_SECONDS]
        for uid in expired:
            self._sessions.pop(uid, None)


# Module-level singleton.
game_session_manager = GameSessionManager()
