"""
Online Module - Message Structure & Validation

Every synchronised operation (INVITE/ACCEPT/MOVE/RESIGN/DRAW...) is wrapped in
a single, numbered "trusted message" structure:

    {
      "msg_id": "uuid-1234",
      "room_id": "room-abc",
      "sender": "player_red",
      "type":   "MOVE",
      "seq":    42,
      "payload": {...},
      "timestamp": 1710000000000
    }

NOTE: The `sender` field is informational only. The backend authoritative
identity is read from the SocketIO connection (sid -> user_id), NEVER from
this field. This is the core defence against "two players confused as one".
"""
import time
import uuid

# ========== Message types ==========
# State-changing messages increment room.seq
STATE_CHANGING_TYPES = {'MOVE', 'RESIGN', 'DRAW_REQUEST', 'DRAW_ACCEPT',
                        'DRAW_DECLINE', 'RESTART_REQUEST', 'RESTART_ACCEPT'}
# Non-state-changing messages do NOT consume a seq slot
NON_STATE_TYPES = {'JOIN', 'LEAVE', 'PING', 'PONG', 'CATCH_UP', 'READY'}
# Server -> client message types
SERVER_TYPES = {'ACK', 'NACK', 'STATE_UPDATE', 'GAME_START', 'GAME_OVER',
                'PLAYER_JOINED', 'PLAYER_LEFT', 'ERROR', 'PONG', 'CATCH_UP_RESPONSE'}

MESSAGE_TYPES = STATE_CHANGING_TYPES | NON_STATE_TYPES | SERVER_TYPES


def build_message(msg_type, room_id, sender, payload=None, seq=None):
    """Build a client-style message envelope."""
    return {
        'msg_id': str(uuid.uuid4()),
        'room_id': room_id,
        'sender': sender,
        'type': msg_type,
        'seq': seq,
        'payload': payload or {},
        'timestamp': int(time.time() * 1000),
    }


def build_ack(msg_id, current_seq, status='OK', extra=None):
    """ACK returned to the sender after a state-changing op is committed."""
    ack = {
        'msg_id': msg_id,
        'type': 'ACK',
        'status': status,
        'current_seq': current_seq,
        'timestamp': int(time.time() * 1000),
    }
    if extra:
        ack.update(extra)
    return ack


def build_nack(msg_id, reason, current_seq=None):
    """Negative ACK — operation rejected."""
    return {
        'msg_id': msg_id,
        'type': 'NACK',
        'status': 'ERROR',
        'reason': reason,
        'current_seq': current_seq,
        'timestamp': int(time.time() * 1000),
    }


def build_state_update(room_id, seq, snapshot, last_move=None):
    """Full-board snapshot broadcast to all room members.

    Receivers OVERWRITE local state with this snapshot rather than
    deriving it from a move description — this eliminates the
    "one side can't see the other's move" class of bugs.
    """
    return {
        'type': 'STATE_UPDATE',
        'room_id': room_id,
        'seq': seq,
        'snapshot': snapshot,
        'last_move': last_move,
        'timestamp': int(time.time() * 1000),
    }


def build_game_start(room_id, seq, snapshot, players):
    """Broadcast when both players are ready."""
    return {
        'type': 'GAME_START',
        'room_id': room_id,
        'seq': seq,
        'snapshot': snapshot,
        'players': players,
        'timestamp': int(time.time() * 1000),
    }


def build_game_over(room_id, seq, snapshot, winner, reason=''):
    return {
        'type': 'GAME_OVER',
        'room_id': room_id,
        'seq': seq,
        'snapshot': snapshot,
        'winner': winner,
        'reason': reason,
        'timestamp': int(time.time() * 1000),
    }


def build_error(reason, code='ERROR'):
    return {
        'type': 'ERROR',
        'code': code,
        'reason': reason,
        'timestamp': int(time.time() * 1000),
    }


def validate_message_structure(msg):
    """Check that an incoming client message has the required fields.

    Returns (ok: bool, error: str|None).
    """
    if not isinstance(msg, dict):
        return False, 'message must be a JSON object'
    for field in ('msg_id', 'type', 'timestamp'):
        if field not in msg:
            return False, f'missing field: {field}'
    msg_type = msg.get('type')
    if msg_type not in MESSAGE_TYPES:
        return False, f'unknown message type: {msg_type}'
    if msg_type in STATE_CHANGING_TYPES:
        # state-changing messages must carry seq + room_id
        if 'seq' not in msg or not isinstance(msg['seq'], int):
            return False, f'seq (int) required for {msg_type}'
        if 'room_id' not in msg:
            return False, 'room_id required'
    return True, None
