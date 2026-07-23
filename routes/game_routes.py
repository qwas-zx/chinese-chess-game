"""
Chinese Chess Game - Local Two-Player Routes

Each logged-in user gets their own ChessGame instance, so the board state
is not shared between accounts. Before this change there was a single
global game object and every visitor saw the same position ("I open the
page and I'm already on the last person's game").

Authentication: all endpoints require a valid Flask session (``user_id`` +
``username``). Unauthenticated calls receive a 401; the frontend redirects
to ``/login`` on 401.
"""
import logging
from flask import session, jsonify, request
from game.game_session_manager import game_session_manager
from logging_config import log_game_event

logger = logging.getLogger(__name__)


def _current_user(require=True):
    """Return (user_id, username) or None.

    When ``require`` is True we guarantee a non-None return or raise a
    ``_AuthRequired`` sentinel that the caller turns into a 401 response.
    """
    uid = session.get('user_id')
    uname = session.get('username')
    if uid is None or uname is None:
        return None
    return uid, uname


def register_routes(app):
    """Register all local-game routes with the Flask app."""

    @app.route('/')
    def index():
        from flask import render_template
        return render_template('index.html')

    # ---------- helpers ----------

    def _user_game():
        """Return the current user's ChessGame, or None + a 401 response."""
        user = _current_user()
        if user is None:
            return None, (jsonify({'success': False, 'message': '未登录'}), 401)
        uid, _ = user
        return game_session_manager.get_local_game(uid), None

    def _state_payload(g):
        return {
            'board': g.board,
            'current_turn': g.current_turn,
            'game_over': g.game_over,
            'winner': g.winner,
            'flipped': g.flipped,
            'move_history': g.move_history,
            'draw_requested_by': g.draw_requested_by,
            'adjust_mode': g.adjust_mode,
        }

    # ---------- endpoints ----------

    @app.route('/api/state', methods=['GET'])
    def get_state():
        g, err = _user_game()
        if err:
            return err
        return jsonify(_state_payload(g))

    @app.route('/api/move', methods=['POST'])
    def move():
        g, err = _user_game()
        if err:
            return err
        user = _current_user()
        uid, _ = user
        data = request.json or {}
        from_x = data.get('from_x')
        from_y = data.get('from_y')
        to_x = data.get('to_x')
        to_y = data.get('to_y')
        if None in (from_x, from_y, to_x, to_y):
            return jsonify({'success': False, 'message': '缺少参数'})
        result = g.make_move(from_x, from_y, to_x, to_y)
        if result.get('success'):
            move_desc = result.get('move_description', '')
            log_game_event(logger, 'MOVE', user_id=uid, game_mode='local',
                           move=move_desc, captured=result.get('captured') is not None,
                           check=result.get('check', False), checkmate=result.get('checkmate', False))
        return jsonify(result)

    @app.route('/api/reset', methods=['POST'])
    def reset():
        g, err = _user_game()
        if err:
            return err
        user = _current_user()
        uid, _ = user
        g.reset()
        log_game_event(logger, 'RESET', user_id=uid, game_mode='local')
        return jsonify({'success': True, **_state_payload(g)})

    @app.route('/api/valid_moves', methods=['POST'])
    def valid_moves():
        g, err = _user_game()
        if err:
            return err
        data = request.json or {}
        x = data.get('x')
        y = data.get('y')
        if x is None or y is None:
            return jsonify({'success': False, 'message': '缺少参数'})
        piece = g.board[y][x]
        if piece is None:
            return jsonify({'success': False, 'message': '该位置没有棋子'})
        if g.get_piece_color(piece) != g.current_turn:
            return jsonify({'success': False, 'message': '不是你的回合'})
        moves = []
        for tx in range(9):
            for ty in range(10):
                if g.is_valid_move(x, y, tx, ty):
                    moves.append({'x': tx, 'y': ty})
        return jsonify({'success': True, 'moves': moves})

    @app.route('/api/undo', methods=['POST'])
    def undo():
        g, err = _user_game()
        if err:
            return err
        user = _current_user()
        uid, _ = user
        result = g.undo()
        if result.get('success'):
            log_game_event(logger, 'UNDO', user_id=uid, game_mode='local')
        return jsonify(result)

    @app.route('/api/flip', methods=['POST'])
    def flip():
        g, err = _user_game()
        if err:
            return err
        return jsonify(g.flip())

    @app.route('/api/resign', methods=['POST'])
    def resign():
        g, err = _user_game()
        if err:
            return err
        return jsonify(g.resign())

    @app.route('/api/draw', methods=['POST'])
    def draw():
        g, err = _user_game()
        if err:
            return err
        data = request.json or {}
        action = data.get('action', 'request')
        if action == 'request':
            result = g.request_draw()
        elif action == 'accept':
            result = g.accept_draw()
        elif action == 'decline':
            result = g.decline_draw()
        else:
            return jsonify({'success': False, 'message': '无效操作'})
        return jsonify(result)

    @app.route('/api/adjust', methods=['POST'])
    def adjust():
        g, err = _user_game()
        if err:
            return err
        data = request.json or {}
        action = data.get('action')
        x = data.get('x')
        y = data.get('y')
        piece = data.get('piece')

        if action == 'toggle_mode':
            g.adjust_mode = not g.adjust_mode
            return jsonify({
                'success': True,
                'adjust_mode': g.adjust_mode,
                'board': g.board,
            })

        if action not in ('add', 'remove', 'replace'):
            return jsonify({'success': False, 'message': '无效操作'})

        result = g.adjust_piece(action, x, y, piece)
        return jsonify(result)

    @app.route('/api/import', methods=['POST'])
    def import_game():
        g, err = _user_game()
        if err:
            return err
        data = request.json or {}
        board = data.get('board')
        current_turn = data.get('current_turn', 'red')
        move_history = data.get('move_history', [])
        if g.import_state(board, current_turn, move_history):
            return jsonify({'success': True, **_state_payload(g)})
        return jsonify({'success': False, 'message': '导入数据无效'})

    @app.route('/api/analyze', methods=['POST'])
    def analyze():
        g, err = _user_game()
        if err:
            return err
        from game.ai import ChessAI
        ai = ChessAI(color=g.current_turn, difficulty='hard')
        
        move = ai.choose_move(g.board, g.current_turn)
        if move is None:
            return jsonify({'success': False, 'message': '无法分析'})
        
        fx, fy, tx, ty = move
        piece = g.board[fy][fx]
        piece_name = piece.split('_')[1] if piece else ''
        
        return jsonify({
            'success': True,
            'recommendation': {
                'from_x': fx, 'from_y': fy,
                'to_x': tx, 'to_y': ty,
                'piece': piece_name,
                'description': _format_move(fx, fy, tx, ty, piece_name)
            },
            'evaluation': ai._evaluate(g.board)
        })

    @app.route('/api/review', methods=['POST'])
    def review():
        g, err = _user_game()
        if err:
            return err
        from game.ai import ChessAI
        from game.core import ChessGame
        ai = ChessAI(color='red', difficulty='hard')
        
        history = g.move_history
        reviews = []
        sim = ChessGame()
        
        for i, move_record in enumerate(history):
            fx = move_record.get('from_x')
            fy = move_record.get('from_y')
            tx = move_record.get('to_x')
            ty = move_record.get('to_y')
            desc = move_record.get('description')
            color = move_record.get('color')
            
            if None in (fx, fy, tx, ty):
                continue
            
            sim.current_turn = color
            before_score = ai._evaluate(sim.board)
            
            best_move = ai.choose_move(sim.board, color)
            best_score = -float('inf')
            if best_move:
                sim2 = ChessGame()
                sim2.board = [row[:] for row in sim.board]
                sim2.board[best_move[3]][best_move[2]] = sim2.board[best_move[1]][best_move[0]]
                sim2.board[best_move[1]][best_move[0]] = None
                best_score = ai._evaluate(sim2.board)
            
            sim.make_move(fx, fy, tx, ty)
            after_score = ai._evaluate(sim.board)
            
            score_diff = after_score - before_score
            best_diff = best_score - before_score
            
            quality = 'good'
            comment = '合理走法'
            if score_diff < -50:
                quality = 'bad'
                comment = '不太好的走法'
            elif best_diff - score_diff > 100:
                quality = 'miss'
                comment = '错失更好的走法'
            elif score_diff > 100:
                quality = 'excellent'
                comment = '精彩的走法'
            
            reviews.append({
                'move_number': i + 1,
                'color': color,
                'description': desc,
                'quality': quality,
                'comment': comment,
                'score_diff': score_diff,
                'best_score_diff': best_diff
            })
        
        return jsonify({'success': True, 'reviews': reviews})

def _format_move(fx, fy, tx, ty, piece_name):
    col_names = '九八七六五四三二一'
    row_names_red = '一二三四五六七八九'
    row_names_black = '九八七六五四三二一'
    
    col_from = col_names[fx]
    col_to = col_names[tx]
    row_from = row_names_red[8 - fy]
    row_to = row_names_red[8 - ty]
    
    return f'{piece_name}{col_from}{row_from}→{col_to}{row_to}'
