"""
Chinese Chess Game - Admin Management Routes

Admin-only pages and APIs for managing users, browsing game records, and
viewing dashboard stats. Every endpoint requires a logged-in admin; non-admin
users get 403. The admin flag is set on the first registered user (see
db.init_db) and can be toggled here.

Endpoints:
    GET  /admin                         -> admin page
    GET  /api/admin/stats               -> dashboard counters
    GET  /api/admin/users              -> users + their stats
    GET  /api/admin/records             -> recent game records
    POST /api/admin/users/<id>/admin   -> {is_admin: true|false}
    DELETE /api/admin/users/<id>        -> delete user + their records
"""
import logging
from flask import session, jsonify, request, render_template

from db import (
    is_admin, get_all_users_with_stats, get_game_records,
    get_admin_stats, set_admin, delete_user,
)
from logging_config import log_auth_event

logger = logging.getLogger(__name__)


def _current_user():
    uid = session.get('user_id')
    uname = session.get('username')
    if uid is None or uname is None:
        return None
    return uid, uname


def _require_admin():
    """Return (user_tuple, None) for admins, or (None, error_response)."""
    user = _current_user()
    if user is None:
        return None, (jsonify({'success': False, 'message': '未登录'}), 401)
    uid, uname = user
    if not is_admin(uid):
        log_auth_event(logger, 'ADMIN_FORBIDDEN', user_id=uid, username=uname, success=False)
        return None, (jsonify({'success': False, 'message': '权限不足'}), 403)
    return user, None


def register_admin_routes(app):

    @app.route('/admin')
    def page_admin():
        # Auth gating happens client-side via the API; but we still render
        # the page so a logged-out visitor gets redirected to login by the
        # frontend instead of a bare 401 from a page route.
        return render_template('admin.html')

    @app.route('/api/admin/stats')
    def admin_stats():
        user, err = _require_admin()
        if err:
            return err
        return jsonify({'success': True, 'stats': get_admin_stats()})

    @app.route('/api/admin/users')
    def admin_users():
        user, err = _require_admin()
        if err:
            return err
        return jsonify({'success': True, 'users': get_all_users_with_stats()})

    @app.route('/api/admin/records')
    def admin_records():
        user, err = _require_admin()
        if err:
            return err
        try:
            limit = int(request.args.get('limit', '200'))
        except ValueError:
            limit = 200
        limit = max(1, min(limit, 1000))
        return jsonify({'success': True, 'records': get_game_records(limit=limit)})

    @app.route('/api/admin/users/<int:user_id>/admin', methods=['POST'])
    def admin_toggle_admin(user_id):
        me, err = _require_admin()
        if err:
            return err
        me_id, _ = me
        if user_id == me_id:
            return jsonify({'success': False, 'message': '不能修改自己的管理员状态'}), 400
        data = request.get_json(silent=True) or {}
        target = bool(data.get('is_admin'))
        if set_admin(user_id, target):
            log_auth_event(
                logger, 'ADMIN_TOGGLE',
                actor_id=me_id, target_id=user_id,
                is_admin=target, success=True,
            )
            return jsonify({'success': True, 'is_admin': target})
        return jsonify({'success': False, 'message': '用户不存在'}), 404

    @app.route('/api/admin/users/<int:user_id>', methods=['DELETE'])
    def admin_delete_user(user_id):
        me, err = _require_admin()
        if err:
            return err
        me_id, _ = me
        if user_id == me_id:
            return jsonify({'success': False, 'message': '不能删除自己'}), 400
        if delete_user(user_id):
            log_auth_event(
                logger, 'ADMIN_DELETE_USER',
                actor_id=me_id, target_id=user_id, success=True,
            )
            return jsonify({'success': True})
        return jsonify({'success': False, 'message': '用户不存在'}), 404
