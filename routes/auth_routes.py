"""
Chinese Chess Game - Authentication Routes

Registration / login / logout / me. Uses Flask session (cookie-based) for
auth state. Passwords are hashed with werkzeug.

Supports a ``redirect`` query parameter on ``/login`` so protected pages
can send the user back after they log in.
"""
from flask import session, jsonify, request
from urllib.parse import urlparse
from db import create_user, verify_user, get_user_by_id


# Allowed redirect targets after login (must be paths on this same site).
ALLOWED_REDIRECT_PATHS = (
    '/', '/ai', '/lobby', '/play', '/login',
)


def _safe_redirect(target):
    """Return ``target`` if it is a safe same-site path, else ``/lobby``."""
    if not target:
        return '/lobby'
    parsed = urlparse(target)
    # Reject anything with a scheme or netloc (cross-site redirect).
    if parsed.scheme or parsed.netloc:
        return '/lobby'
    path = parsed.path or '/lobby'
    if path not in ALLOWED_REDIRECT_PATHS:
        return '/lobby'
    return path


def register_auth_routes(app):

    @app.route('/login')
    def page_login():
        from flask import render_template
        return render_template('login.html')

    @app.route('/auth/register', methods=['POST'])
    def auth_register():
        data = request.get_json(silent=True) or {}
        username = (data.get('username') or '').strip()
        password = data.get('password') or ''
        redirect = _safe_redirect(data.get('redirect') or request.args.get('redirect'))

        if not username or not password:
            return jsonify({'success': False, 'message': '用户名和密码不能为空'}), 400
        if not (2 <= len(username) <= 20):
            return jsonify({'success': False, 'message': '用户名长度需为 2-20 个字符'}), 400
        if len(password) < 4:
            return jsonify({'success': False, 'message': '密码至少 4 位'}), 400
        try:
            uid = create_user(username, password)
        except Exception:
            return jsonify({'success': False, 'message': '用户名已存在'}), 409
        session.clear()
        session['user_id'] = uid
        session['username'] = username
        return jsonify({
            'success': True,
            'user': {'id': uid, 'username': username},
            'redirect': redirect,
        })

    @app.route('/auth/login', methods=['POST'])
    def auth_login():
        data = request.get_json(silent=True) or {}
        username = (data.get('username') or '').strip()
        password = data.get('password') or ''
        redirect = _safe_redirect(data.get('redirect') or request.args.get('redirect'))

        user = verify_user(username, password)
        if user is None:
            return jsonify({'success': False, 'message': '用户名或密码错误'}), 401
        session.clear()
        session['user_id'] = user['id']
        session['username'] = user['username']
        return jsonify({
            'success': True,
            'user': {'id': user['id'], 'username': user['username']},
            'redirect': redirect,
        })

    @app.route('/auth/logout', methods=['POST'])
    def auth_logout():
        session.clear()
        return jsonify({'success': True, 'redirect': '/login'})

    @app.route('/auth/me', methods=['GET'])
    def auth_me():
        uid = session.get('user_id')
        if uid is None:
            return jsonify({'success': False, 'logged_in': False}), 401
        user = get_user_by_id(uid)
        if user is None:
            session.clear()
            return jsonify({'success': False, 'logged_in': False}), 401
        return jsonify({
            'success': True,
            'logged_in': True,
            'user': {'id': user['id'], 'username': user['username']},
        })
