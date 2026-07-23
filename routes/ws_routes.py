"""
Chinese Chess Game - WebSocket (SocketIO) Routes

This is the *data plane* of the online protocol. All state-changing ops
(MOVE / RESIGN / DRAW_*) follow the three-step protocol:

  1. Client -> server: room_message {type, msg_id, seq, payload, ...}
  2. Server validates (room exists, sender == current turn via connection
     identity, msg_id not seen, seq == room.seq + 1), applies, ACKs sender.
  3. Server broadcasts STATE_UPDATE (full snapshot) to the whole room.

Identity rule (§4): the server reads `user_id` from the connection registry
(sid -> user_id), NEVER from the message's `sender` field.

Heartbeat: client PING {last_seq} -> server PONG {current_seq}.
Reconnect: client CATCH_UP {from_seq} -> server CATCH_UP_RESPONSE {snapshot}.
"""
import time
import logging

from flask import session, request
from flask_socketio import emit, join_room, leave_room

from online.connection_registry import connection_registry
from online.room_manager import room_manager, Room
from online.message import (
    validate_message_structure,
    build_ack, build_nack,
    build_state_update, build_game_start, build_game_over, build_error,
    STATE_CHANGING_TYPES,
)
from logging_config import log_online_event, log_game_event

logger = logging.getLogger(__name__)


def register_ws_handlers(socketio):

    # ---------- internal helpers ----------

    def _attach_to_room(sid, uid, room):
        """Attach a connection to its room: join socketio room, mark connected,
        push current state, and broadcast GAME_START the first time the room
        becomes playable."""
        join_room(room.room_id)
        connection_registry.set_room(sid, room.room_id)
        room.mark_connected(uid)

        # Push current snapshot to this connection (acts as catch-up on join).
        snap = room.snapshots[-1]['snapshot'] if room.snapshots else None
        if snap is not None:
            emit('state_update',
                 build_state_update(room.room_id, room.seq, snap), to=sid)

        # GAME_START: the first attacher broadcasts to the whole room; any
        # later attacher (who missed that broadcast) gets it sent to itself.
        if room.status == Room.PLAYING and len(room.players) == 2:
            players = {uid: p.to_dict() for uid, p in room.players.items()}
            if not room.game_start_broadcasted:
                room.game_start_broadcasted = True
                socketio.emit('game_start',
                              build_game_start(room.room_id, room.seq, snap, players),
                              room=room.room_id)
            else:
                emit('game_start',
                     build_game_start(room.room_id, room.seq, snap, players),
                     to=sid)

    # ---------- connection lifecycle ----------

    @socketio.on('connect')
    def handle_connect():
        uid = session.get('user_id')
        uname = session.get('username')
        if uid is None or uname is None:
            # Reject the connection (client must log in first).
            logger.warning("WS CONNECT REJECTED: no session")
            return False
        sid = request.sid

        # Evict any prior connection for the same user (one connection per user).
        old_sid = connection_registry.get_sid_by_user(uid)
        connection_registry.bind(sid, uid, uname)
        if old_sid and old_sid != sid:
            log_online_event(logger, 'KICK_OLD_CONNECTION', user_id=uid)
            socketio.emit('force_disconnect',
                          {'reason': '账号在其他地方登录'}, to=old_sid)

        log_online_event(logger, 'CONNECT', user_id=uid, sid=sid)

        # If the user already has a room (reconnect / page refresh), reattach.
        room = room_manager.get_room_of_user(uid)
        if room is not None:
            log_online_event(logger, 'RECONNECT', user_id=uid, room_id=room.room_id)
            _attach_to_room(sid, uid, room)

    @socketio.on('disconnect')
    def handle_disconnect():
        sid = request.sid
        info = connection_registry.remove(sid)
        if info is None:
            return
        uid = info['user_id']
        room_id = info['room_id']
        log_online_event(logger, 'DISCONNECT', user_id=uid, room_id=room_id, sid=sid)
        if not room_id:
            return
        room = room_manager.get_room(room_id)
        if room is None:
            return
        room.mark_disconnected(uid)
        # Tell the opponent this player temporarily dropped.
        emit('player_left',
             {'user_id': uid, 'username': info['username'], 'room_id': room_id},
             room=room_id, skip_sid=sid)
        # NOTE: we do NOT remove the player here — a reconnection within the
        # grace period reattaches them. Explicit leave (HTTP /leave) is the
        # only way to permanently exit a room mid-game.

    # ---------- unified message entry ----------

    @socketio.on('room_message')
    def handle_room_message(msg):
        sid = request.sid
        info = connection_registry.get(sid)
        if info is None:
            emit('error', build_error('连接未注册，请重新连接'))
            return
        uid = info['user_id']

        ok, err = validate_message_structure(msg)
        if not ok:
            emit('error', build_error(err or '消息格式错误'))
            return

        mtype = msg.get('type')
        msg_id = msg.get('msg_id')
        seq = msg.get('seq')
        payload = msg.get('payload') or {}
        room_id_in_msg = msg.get('room_id')

        # ----- non-state-changing messages -----
        if mtype == 'JOIN':
            room = room_manager.get_room_of_user(uid)
            if room is None:
                emit('error', build_error('你尚未加入任何房间'))
                return
            if room_id_in_msg and room_id_in_msg.upper() != room.room_id:
                emit('error', build_error('房间不匹配'))
                return
            _attach_to_room(sid, uid, room)
            return

        if mtype == 'PING':
            room = room_manager.get_room_of_user(uid)
            cur_seq = room.seq if room else 0
            emit('pong', {
                'current_seq': cur_seq,
                'last_seq': payload.get('last_seq'),
                'server_ts': int(time.time() * 1000),
            })
            return

        if mtype == 'CATCH_UP':
            room = room_manager.get_room_of_user(uid)
            if room is None:
                emit('error', build_error('你尚未加入任何房间'))
                return
            snap = room.catch_up(payload.get('from_seq', 0))
            if snap is None:
                emit('error', build_error('无可同步状态'))
                return
            emit('catch_up_response', {
                'room_id': room.room_id,
                'seq': snap['seq'],
                'snapshot': snap['snapshot'],
            })
            return

        if mtype == 'LEAVE':
            room = room_manager.get_room_of_user(uid)
            if room is None:
                emit('error', build_error('你不在任何房间'))
                return
            leave_room(room.room_id)
            emit('info', {'message': '已离开房间'})
            return

        if mtype == 'CHAT':
            room = room_manager.get_room_of_user(uid)
            if room is None:
                emit('error', build_error('你不在任何房间'))
                return
            text = payload.get('text', '').strip()
            if not text or len(text) > 200:
                return
            player = room.get_player(uid)
            sender_color = player.color if player else None
            socketio.emit('chat', {
                'room_id': room.room_id,
                'sender': sender_color,
                'text': text,
                'timestamp': int(time.time()),
            }, room=room.room_id)
            return

        # ----- state-changing messages: three-step protocol -----
        if mtype in STATE_CHANGING_TYPES:
            # Resolve room from CONNECTION, not from msg.room_id.
            room = room_manager.get_room_of_user(uid)
            if room is None:
                emit('nack', build_nack(msg_id, '你不在任何房间'))
                return
            if room_id_in_msg and room_id_in_msg.upper() != room.room_id:
                emit('nack', build_nack(msg_id, '房间不匹配'))
                return

            expected_seq = seq
            result = None
            error = None

            if mtype == 'MOVE':
                try:
                    f = payload['from']
                    t = payload['to']
                    fx, fy = int(f['x']), int(f['y'])
                    tx, ty = int(t['x']), int(t['y'])
                except (KeyError, TypeError, ValueError):
                    emit('nack', build_nack(msg_id, '走棋数据格式错误', room.seq))
                    return
                ok, result, error = room.apply_move(
                    uid, msg_id, expected_seq, fx, fy, tx, ty)
                if ok and result and not result.get('duplicate'):
                    log_online_event(logger, 'MOVE', user_id=uid, room_id=room.room_id,
                                     move=f"({fx},{fy})->({tx},{ty})")
            elif mtype == 'RESIGN':
                ok, result, error = room.apply_resign(uid, msg_id, expected_seq)
                if ok and result and not result.get('duplicate'):
                    log_online_event(logger, 'RESIGN', user_id=uid, room_id=room.room_id)
            elif mtype == 'DRAW_REQUEST':
                ok, result, error = room.apply_draw_request(uid, msg_id, expected_seq)
            elif mtype == 'DRAW_ACCEPT':
                ok, result, error = room.apply_draw_accept(uid, msg_id, expected_seq)
            elif mtype == 'DRAW_DECLINE':
                ok, result, error = room.apply_draw_decline(uid, msg_id, expected_seq)
            elif mtype in ('RESTART_REQUEST', 'RESTART_ACCEPT'):
                ok, result, error = room.apply_restart(uid, msg_id, expected_seq)
            else:
                emit('nack', build_nack(msg_id, f'不支持的操作: {mtype}'))
                return

            if not ok:
                emit('nack', build_nack(msg_id, error or '操作失败', room.seq))
                return

            # Duplicate retry (msg_id already processed): ACK, do NOT broadcast.
            if result and result.get('duplicate'):
                emit('ack', build_ack(msg_id, result['current_seq']))
                return

            # Success: ACK the sender, broadcast STATE_UPDATE to the room.
            snap = room.snapshots[-1]['snapshot']
            emit('ack', build_ack(msg_id, room.seq, extra={'result': result}))
            last_move = result.get('last_move') if result else None
            socketio.emit('state_update',
                          build_state_update(room.room_id, room.seq, snap,
                                             last_move=last_move),
                          room=room.room_id)

            # If the move ended the game, broadcast GAME_OVER too.
            if result and result.get('game_over'):
                socketio.emit('game_over',
                              build_game_over(room.room_id, room.seq, snap,
                                              result.get('winner'),
                                              result.get('message') or ''),
                              room=room.room_id)
            return

        emit('error', build_error(f'未处理的消息类型: {mtype}'))
