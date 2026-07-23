"""
Online Module - Room Manager

Each Room owns:
- a ChessGame instance (the authoritative game state),
- a monotonically increasing `seq`,
- a set of processed `msg_id`s (dedup),
- player slots {user_id: PlayerInfo},
- a per-seq snapshot history (for CATCH_UP),
- a status state machine: WAITING -> PLAYING -> FINISHED.

Three-step protocol for state-changing ops (MOVE/RESIGN/DRAW...):
  1. Client sends {type, seq=expected_next, msg_id, payload}
  2. Server validates: room exists, sender is current turn, msg_id not seen,
     seq == room.seq + 1. On success: apply, room.seq += 1, snapshot, ACK sender.
  3. Server broadcasts STATE_UPDATE (full snapshot) to all room members.

Heartbeat / catch-up:
  - PING carries last_seq; server replies PONG with current_seq.
  - CATCH_UP returns the current full snapshot (client overwrites local state).
"""
import secrets
import threading
import time
from copy import deepcopy

from game import ChessGame
from game.constants import INITIAL_BOARD


class PlayerInfo:
    __slots__ = ('user_id', 'username', 'color', 'ready', 'connected')

    def __init__(self, user_id, username, color):
        self.user_id = user_id
        self.username = username
        self.color = color          # 'red' | 'black'
        self.ready = True           # ready once joined (room-code invite flow)
        self.connected = True

    def to_dict(self):
        return {
            'user_id': self.user_id,
            'username': self.username,
            'color': self.color,
            'ready': self.ready,
            'connected': self.connected,
        }


class Room:
    # Status
    WAITING = 'waiting'
    PLAYING = 'playing'
    FINISHED = 'finished'

    RECONNECT_GRACE = 60  # seconds before a disconnected player's slot is freed

    def __init__(self, room_id, creator_user_id, creator_username):
        self.room_id = room_id
        self.players = {}             # user_id -> PlayerInfo
        self.seq = 0
        self.processed_msg_ids = set()
        self.snapshots = []           # list of {'seq', 'snapshot', 'ts'}
        self.created_at = time.time()
        self.status = Room.WAITING
        self.last_activity = time.time()
        self.game_start_broadcasted = False  # set once GAME_START is broadcast
        self._lock = threading.RLock()

        # Creator takes red slot.
        self.players[creator_user_id] = PlayerInfo(creator_user_id, creator_username, 'red')
        self.game = ChessGame()
        self._record_snapshot()

    # ---------- helpers ----------

    def _record_snapshot(self):
        self.snapshots.append({
            'seq': self.seq,
            'snapshot': self.snapshot(),
            'ts': int(time.time() * 1000),
        })

    def snapshot(self):
        """Full authoritative snapshot of the room state."""
        return {
            'room_id': self.room_id,
            'board': deepcopy(self.game.board),
            'current_turn': self.game.current_turn,
            'game_over': self.game.game_over,
            'winner': self.game.winner,
            'move_history': deepcopy(self.game.move_history),
            'draw_requested_by': self.game.draw_requested_by,
            'flipped': self.game.flipped,
            'players': {uid: p.to_dict() for uid, p in self.players.items()},
            'status': self.status,
            'seq': self.seq,
        }

    def is_full(self):
        return len(self.players) >= 2

    def is_player(self, user_id):
        return user_id in self.players

    def get_color(self, user_id):
        p = self.players.get(user_id)
        return p.color if p else None

    def opponent_of(self, user_id):
        for uid, p in self.players.items():
            if uid != user_id:
                return p
        return None

    # ---------- join / leave ----------

    def add_player(self, user_id, username):
        """Add a second player (black). Returns (ok, error)."""
        with self._lock:
            if self.is_full():
                return False, '房间已满'
            if user_id in self.players:
                return False, '你已在房间内'
            self.players[user_id] = PlayerInfo(user_id, username, 'black')
            self.last_activity = time.time()
            # Both present -> start the game.
            if len(self.players) == 2:
                self.status = Room.PLAYING
            return True, None

    def mark_disconnected(self, user_id):
        with self._lock:
            p = self.players.get(user_id)
            if p:
                p.connected = False

    def mark_connected(self, user_id):
        with self._lock:
            p = self.players.get(user_id)
            if p:
                p.connected = True

    def remove_player(self, user_id):
        """Permanently remove a player. If a game is in progress, the opponent wins."""
        with self._lock:
            p = self.players.pop(user_id, None)
            if p is None:
                return None
            # If game was ongoing, remaining player wins by opponent leaving.
            if self.status == Room.PLAYING and not self.game.game_over:
                for other in self.players.values():
                    self.game.game_over = True
                    self.game.winner = other.color
                    self.status = Room.FINISHED
                    self._record_snapshot()
                    break
            else:
                if len(self.players) == 0:
                    self.status = Room.FINISHED
            self.last_activity = time.time()
            return p

    # ---------- seq / dedup ----------

    def is_current_turn(self, user_id):
        p = self.players.get(user_id)
        if p is None:
            return False
        return p.color == self.game.current_turn and not self.game.game_over

    # ---------- state-changing operations ----------
    #
    # Every apply_* method takes (user_id, msg_id, expected_seq, ...) and
    # atomically (under self._lock) performs the three-step protocol:
    #   1. dedup via msg_id  -> return (True, {'duplicate': True, ...}, None)
    #      so the caller can ACK the retry without re-broadcasting.
    #   2. validate seq == self.seq + 1  -> else (False, None, 'seq mismatch')
    #   3. validate game state + turn, apply the change
    #   4. record msg_id ONLY after success, then seq += 1 + snapshot
    # Return shape: (ok: bool, result_dict|None, error_str|None).

    def apply_move(self, user_id, msg_id, expected_seq, from_x, from_y, to_x, to_y):
        with self._lock:
            if msg_id in self.processed_msg_ids:
                return True, {'duplicate': True, 'current_seq': self.seq}, None
            if expected_seq != self.seq + 1:
                return False, None, f'seq mismatch: expected {self.seq + 1}, got {expected_seq}'
            if self.status != Room.PLAYING:
                return False, None, '对局未开始或已结束'
            if not self.is_current_turn(user_id):
                return False, None, '不是你的回合'
            result = self.game.make_move(from_x, from_y, to_x, to_y)
            if not result.get('success'):
                return False, None, result.get('message', '无效走棋')
            self.processed_msg_ids.add(msg_id)
            last_move = None
            if self.game.move_history:
                last = self.game.move_history[-1]
                last_move = {
                    'from': last['from'],
                    'to': last['to'],
                    'piece': last['piece'],
                    'captured': last['captured'],
                    'description': last['description'],
                }
            if self.game.game_over:
                self.status = Room.FINISHED
            self.seq += 1
            self.last_activity = time.time()
            self._record_snapshot()
            return True, {
                'last_move': last_move,
                'game_over': self.game.game_over,
                'winner': self.game.winner,
                'message': result.get('message'),
            }, None

    def apply_resign(self, user_id, msg_id, expected_seq):
        with self._lock:
            if msg_id in self.processed_msg_ids:
                return True, {'duplicate': True, 'current_seq': self.seq}, None
            if expected_seq != self.seq + 1:
                return False, None, f'seq mismatch: expected {self.seq + 1}, got {expected_seq}'
            if self.status != Room.PLAYING:
                return False, None, '对局未开始或已结束'
            p = self.players.get(user_id)
            if p is None:
                return False, None, '你不在房间内'
            if self.game.game_over:
                return False, None, '游戏已结束'
            self.game.game_over = True
            self.game.winner = 'black' if p.color == 'red' else 'red'
            self.status = Room.FINISHED
            self.processed_msg_ids.add(msg_id)
            self.seq += 1
            self.last_activity = time.time()
            self._record_snapshot()
            return True, {'winner': self.game.winner, 'resigned_by': p.color}, None

    def apply_draw_request(self, user_id, msg_id, expected_seq):
        with self._lock:
            if msg_id in self.processed_msg_ids:
                return True, {'duplicate': True, 'current_seq': self.seq}, None
            if expected_seq != self.seq + 1:
                return False, None, f'seq mismatch: expected {self.seq + 1}, got {expected_seq}'
            if self.status != Room.PLAYING:
                return False, None, '对局未开始或已结束'
            p = self.players.get(user_id)
            if p is None:
                return False, None, '你不在房间内'
            result = self.game.request_draw()
            if not result.get('success'):
                return False, None, result.get('message', '求和失败')
            self.processed_msg_ids.add(msg_id)
            # request_draw may auto-accept if the opponent already requested.
            if self.game.game_over:
                self.status = Room.FINISHED
            self.seq += 1
            self.last_activity = time.time()
            self._record_snapshot()
            return True, {
                'draw_requested_by': self.game.draw_requested_by,
                'draw_accepted': result.get('draw_accepted', False),
            }, None

    def apply_draw_accept(self, user_id, msg_id, expected_seq):
        with self._lock:
            if msg_id in self.processed_msg_ids:
                return True, {'duplicate': True, 'current_seq': self.seq}, None
            if expected_seq != self.seq + 1:
                return False, None, f'seq mismatch: expected {self.seq + 1}, got {expected_seq}'
            if self.status != Room.PLAYING:
                return False, None, '对局未开始或已结束'
            p = self.players.get(user_id)
            if p is None:
                return False, None, '你不在房间内'
            if self.game.draw_requested_by is None:
                return False, None, '没有待回应的求和请求'
            if self.game.draw_requested_by == p.color:
                return False, None, '不能同意自己的求和'
            result = self.game.accept_draw()
            if not result.get('success'):
                return False, None, result.get('message', '同意求和失败')
            self.processed_msg_ids.add(msg_id)
            self.status = Room.FINISHED
            self.seq += 1
            self.last_activity = time.time()
            self._record_snapshot()
            return True, {'winner': 'draw'}, None

    def apply_draw_decline(self, user_id, msg_id, expected_seq):
        with self._lock:
            if msg_id in self.processed_msg_ids:
                return True, {'duplicate': True, 'current_seq': self.seq}, None
            if expected_seq != self.seq + 1:
                return False, None, f'seq mismatch: expected {self.seq + 1}, got {expected_seq}'
            if self.status != Room.PLAYING:
                return False, None, '对局未开始或已结束'
            p = self.players.get(user_id)
            if p is None:
                return False, None, '你不在房间内'
            result = self.game.decline_draw()
            if not result.get('success'):
                return False, None, result.get('message', '拒绝求和失败')
            self.processed_msg_ids.add(msg_id)
            self.seq += 1
            self.last_activity = time.time()
            self._record_snapshot()
            return True, {'draw_requested_by': None}, None

    def apply_restart(self, user_id, msg_id, expected_seq):
        """Restart the game with a fresh board. Requires both players present."""
        with self._lock:
            if msg_id in self.processed_msg_ids:
                return True, {'duplicate': True, 'current_seq': self.seq}, None
            if expected_seq != self.seq + 1:
                return False, None, f'seq mismatch: expected {self.seq + 1}, got {expected_seq}'
            p = self.players.get(user_id)
            if p is None:
                return False, None, '你不在房间内'
            if len(self.players) < 2:
                return False, None, '对手未在房间'
            self.game = ChessGame()
            self.processed_msg_ids.clear()
            self.processed_msg_ids.add(msg_id)
            self.seq += 1
            self.status = Room.PLAYING
            self.last_activity = time.time()
            self._record_snapshot()
            return True, {'restarted': True}, None

    # ---------- catch-up ----------

    def catch_up(self, from_seq):
        """Return the latest snapshot (>= from_seq). For simplicity we always
        return the newest full snapshot — the client overwrites local state."""
        with self._lock:
            if not self.snapshots:
                return None
            return self.snapshots[-1]


class _RoomManager:
    def __init__(self):
        self._lock = threading.RLock()
        self._rooms = {}             # room_id -> Room
        self._room_by_user = {}      # user_id -> room_id  (one room per user)

    # ---------- room lifecycle ----------

    def create_room(self, creator_user_id, creator_username):
        """Create a new room. Evicts creator from any prior room first."""
        with self._lock:
            self._evict_user_from_rooms(creator_user_id)
            room_id = self._gen_room_id()
            room = Room(room_id, creator_user_id, creator_username)
            self._rooms[room_id] = room
            self._room_by_user[creator_user_id] = room_id
            return room

    def join_room(self, room_id, user_id, username):
        with self._lock:
            room_id = room_id.upper()
            room = self._rooms.get(room_id)
            if room is None:
                return None, '房间不存在'
            if room.is_player(user_id):
                return room, None  # already in (reconnect case)
            if room.is_full():
                return None, '房间已满'
            # Evict from any other room first.
            self._evict_user_from_rooms(user_id, except_room=room_id)
            ok, err = room.add_player(user_id, username)
            if not ok:
                return None, err
            self._room_by_user[user_id] = room_id
            return room, None

    def leave_room(self, room_id, user_id):
        with self._lock:
            room_id = room_id.upper()
            room = self._rooms.get(room_id)
            if room is None:
                return False
            p = room.remove_player(user_id)
            if p is None:
                return False
            self._room_by_user.pop(user_id, None)
            # Delete empty rooms.
            if len(room.players) == 0:
                self._rooms.pop(room_id, None)
            return True

    def get_room(self, room_id):
        with self._lock:
            return self._rooms.get(room_id.upper())

    def get_room_of_user(self, user_id):
        with self._lock:
            rid = self._room_by_user.get(user_id)
            if rid is None:
                return None
            return self._rooms.get(rid)

    def _evict_user_from_rooms(self, user_id, except_room=None):
        rid = self._room_by_user.get(user_id)
        if rid is None or rid == except_room:
            return
        room = self._rooms.get(rid)
        if room is not None:
            room.remove_player(user_id)
            if len(room.players) == 0:
                self._rooms.pop(rid, None)
        self._room_by_user.pop(user_id, None)

    def _gen_room_id(self):
        for _ in range(10):
            rid = secrets.token_hex(3).upper()  # 6 hex chars
            if rid not in self._rooms:
                return rid
        # Fallback (extremely unlikely collision).
        return secrets.token_hex(4).upper()


# Singleton
room_manager = _RoomManager()
