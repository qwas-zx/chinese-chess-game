"""
Chinese Chess Game - Online Room HTTP Routes

These routes handle the *control plane*: creating / joining / querying rooms.
The *data plane* (moves, heartbeat, state sync) goes over the WebSocket
(SocketIO) layer in ws_routes.py.

Authentication is required for all endpoints — identity is read from the
Flask session, never from the request body.
"""
from flask import session, jsonify
from online.room_manager import room_manager


def _current_user():
    """Return (user_id, username) or None if not logged in."""
    uid = session.get('user_id')
    uname = session.get('username')
    if uid is None or uname is None:
        return None
    return uid, uname


def register_room_routes(app):

    @app.route('/lobby')
    def page_lobby():
        from flask import render_template
        return render_template('lobby.html')

    @app.route('/play')
    def page_play():
        from flask import render_template
        return render_template('play.html')

    @app.route('/api/online/rooms', methods=['POST'])
    def online_create_room():
        user = _current_user()
        if user is None:
            return jsonify({'success': False, 'message': '未登录'}), 401
        uid, uname = user
        room = room_manager.create_room(uid, uname)
        return jsonify({
            'success': True,
            'room_id': room.room_id,
            'color': 'red',
            'snapshot': room.snapshot(),
        })

    @app.route('/api/online/rooms/<room_id>/join', methods=['POST'])
    def online_join_room(room_id):
        user = _current_user()
        if user is None:
            return jsonify({'success': False, 'message': '未登录'}), 401
        uid, uname = user
        room, err = room_manager.join_room(room_id, uid, uname)
        if room is None:
            return jsonify({'success': False, 'message': err or '加入失败'}), 400
        return jsonify({
            'success': True,
            'room_id': room.room_id,
            'color': room.get_color(uid),
            'snapshot': room.snapshot(),
        })

    @app.route('/api/online/rooms/<room_id>', methods=['GET'])
    def online_get_room(room_id):
        user = _current_user()
        if user is None:
            return jsonify({'success': False, 'message': '未登录'}), 401
        uid, _ = user
        room = room_manager.get_room(room_id)
        if room is None:
            return jsonify({'success': False, 'message': '房间不存在'}), 404
        if not room.is_player(uid):
            return jsonify({'success': False, 'message': '你不在该房间'}), 403
        return jsonify({'success': True, 'snapshot': room.snapshot()})

    @app.route('/api/online/rooms/<room_id>/leave', methods=['POST'])
    def online_leave_room(room_id):
        user = _current_user()
        if user is None:
            return jsonify({'success': False, 'message': '未登录'}), 401
        uid, _ = user
        ok = room_manager.leave_room(room_id, uid)
        return jsonify({'success': ok})

    @app.route('/api/online/my-room', methods=['GET'])
    def online_my_room():
        """Used on page load / refresh to recover the user's current room.
        The frontend is stateless — the backend is the single source of truth."""
        user = _current_user()
        if user is None:
            return jsonify({'success': False, 'message': '未登录'}), 401
        uid, _ = user
        room = room_manager.get_room_of_user(uid)
        if room is None:
            return jsonify({'success': True, 'in_room': False})
        return jsonify({
            'success': True,
            'in_room': True,
            'room_id': room.room_id,
            'color': room.get_color(uid),
            'snapshot': room.snapshot(),
        })
