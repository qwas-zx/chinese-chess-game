"""
Online Module - Connection Registry

Maintains the AUTHORITATIVE binding between a SocketIO connection (sid) and
the logged-in user identity. This is the single source of truth used by the
WS layer to decide who is sending a message.

Key rule (from protocol spec §4):
    The backend NEVER trusts the `sender` field of an incoming message.
    It always reads `user_id` from the connection object here.

A `user_id` may have at most one active connection at a time — when a user
opens a new connection, any previous one is evicted. This prevents the
"two players treated as the same person" bug at the connection layer.
"""
import threading


class _ConnectionRegistry:
    def __init__(self):
        self._lock = threading.RLock()
        # sid -> {'user_id', 'username', 'room_id'}
        self._by_sid = {}
        # user_id -> sid   (one active connection per user)
        self._sid_by_user = {}

    def bind(self, sid, user_id, username):
        """Bind a new connection. Evicts any prior connection for the same user."""
        with self._lock:
            old_sid = self._sid_by_user.get(user_id)
            if old_sid and old_sid != sid:
                # Evict prior connection (caller should disconnect it).
                self._by_sid.pop(old_sid, None)
            self._by_sid[sid] = {
                'user_id': user_id,
                'username': username,
                'room_id': None,
            }
            self._sid_by_user[user_id] = sid

    def set_room(self, sid, room_id):
        with self._lock:
            info = self._by_sid.get(sid)
            if info is None:
                return False
            info['room_id'] = room_id
            return True

    def get(self, sid):
        with self._lock:
            return dict(self._by_sid[sid]) if sid in self._by_sid else None

    def get_sid_by_user(self, user_id):
        with self._lock:
            return self._sid_by_user.get(user_id)

    def remove(self, sid):
        with self._lock:
            info = self._by_sid.pop(sid, None)
            if info is not None:
                uid = info['user_id']
                if self._sid_by_user.get(uid) == sid:
                    self._sid_by_user.pop(uid, None)
            return info


# Singleton
connection_registry = _ConnectionRegistry()
