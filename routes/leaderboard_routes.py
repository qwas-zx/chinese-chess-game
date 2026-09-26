"""
Chinese Chess Game - Leaderboard Routes

Public ranking page + JSON API. Ranks users by number of wins (ties broken
by total games played, then by user id). Game results come from the
``game_results`` table, populated by the AI-battle and online play modes.
"""
from flask import render_template, jsonify, request

from db import get_leaderboard, get_user_stats


def register_leaderboard_routes(app):

    @app.route('/leaderboard')
    def page_leaderboard():
        return render_template('leaderboard.html')

    @app.route('/api/leaderboard')
    def api_leaderboard():
        try:
            limit = int(request.args.get('limit', '100'))
        except ValueError:
            limit = 100
        # Clamp to a sane range.
        limit = max(1, min(limit, 500))
        rows = get_leaderboard(limit=limit)
        return jsonify({'success': True, 'leaderboard': rows})

    @app.route('/api/leaderboard/me')
    def api_leaderboard_me():
        """Current user's personal stats. Requires login (401 otherwise)."""
        from flask import session
        uid = session.get('user_id')
        if uid is None:
            return jsonify({'success': False, 'message': '未登录'}), 401
        stats = get_user_stats(uid)
        return jsonify({'success': True, 'stats': stats})
