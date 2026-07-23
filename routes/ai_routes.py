"""
Chinese Chess Game - AI Battle Routes

Player (red) vs AI (black). Each logged-in user gets their own game + AI
instance so board state is private and never shared between accounts.

Endpoints (all require login, 401 otherwise):
    GET  /ai                       -> AI battle page
    GET  /api/ai/state             -> current game state
    POST /api/ai/reset             -> reset (optionally set difficulty)
    POST /api/ai/move              -> player moves; AI responds automatically
    POST /api/ai/valid_moves       -> legal moves for a red piece
    POST /api/ai/undo              -> undo player + AI plies (back to player)
    POST /api/ai/resign            -> player resigns
    POST /api/ai/flip              -> flip board view
    POST /api/ai/difficulty        -> change difficulty (resets the game)
"""
import logging
import time

from flask import session, jsonify, request

from game.game_session_manager import game_session_manager
from logging_config import log_game_event, log_ai_event

logger = logging.getLogger(__name__)

# Player is always red in AI battle mode.
PLAYER_COLOR = 'red'
AI_COLOR = 'black'


def _current_user():
    uid = session.get('user_id')
    uname = session.get('username')
    if uid is None or uname is None:
        return None
    return uid, uname


def _user_ai_game():
    """Return (ChessGame, ChessAI) for the current user, or (None, error_response)."""
    user = _current_user()
    if user is None:
        return None, None, (jsonify({'success': False, 'message': '未登录'}), 401)
    uid, _ = user
    g, ai = game_session_manager.get_ai_game(uid)
    return g, ai, None


def _state_payload(g, ai):
    return {
        'board': g.board,
        'current_turn': g.current_turn,
        'game_over': g.game_over,
        'winner': g.winner,
        'flipped': g.flipped,
        'move_history': g.move_history,
        'difficulty': ai.difficulty,
        'player_color': PLAYER_COLOR,
        'ai_color': AI_COLOR,
    }


def _ai_take_turn(g, ai, user_id=None):
    """Let the AI move on ``g``. Returns the make_move result dict, or None."""
    if g.game_over:
        return None
    if g.current_turn != ai.color:
        return None

    start_time = time.time()
    move = ai.choose_move(g.board, g.current_turn)
    duration_ms = int((time.time() - start_time) * 1000)

    if move is None:
        g.game_over = True
        g.winner = PLAYER_COLOR
        log_ai_event(logger, 'NO_MOVES', depth=ai.depth, duration_ms=duration_ms)
        return {'success': True, 'board': g.board,
                'current_turn': g.current_turn,
                'game_over': True, 'winner': PLAYER_COLOR,
                'move_history': g.move_history,
                'message': 'AI 无子可动', 'ai_move': None}

    fx, fy, tx, ty = move
    result = g.make_move(fx, fy, tx, ty)
    result['ai_move'] = result.get('move_description')

    # Log AI move with thinking details
    log_ai_event(logger, 'MOVE', depth=ai.max_depth, duration_ms=duration_ms,
                 move=result.get('move_description'), difficulty=ai.difficulty,
                 user_id=user_id)

    return result


def register_ai_routes(app):
    """Register all AI-battle routes with the Flask app."""

    @app.route('/ai')
    def ai_battle_page():
        from flask import render_template
        return render_template('ai_battle.html')

    @app.route('/api/ai/state', methods=['GET'])
    def ai_state():
        g, ai, err = _user_ai_game()
        if err:
            return err
        return jsonify(_state_payload(g, ai))

    @app.route('/api/ai/reset', methods=['POST'])
    def ai_reset():
        user = _current_user()
        if user is None:
            return jsonify({'success': False, 'message': '未登录'}), 401
        uid, _ = user
        data = request.json or {}
        difficulty = data.get('difficulty')
        if difficulty not in ('easy', 'normal', 'hard'):
            difficulty = None
        g, ai = game_session_manager.reset_ai_game(uid, difficulty=difficulty)
        return jsonify(_state_payload(g, ai))

    @app.route('/api/ai/difficulty', methods=['POST'])
    def ai_difficulty():
        user = _current_user()
        if user is None:
            return jsonify({'success': False, 'message': '未登录'}), 401
        uid, _ = user
        data = request.json or {}
        difficulty = data.get('difficulty')
        if difficulty not in ('easy', 'normal', 'hard'):
            return jsonify({'success': False, 'message': '无效难度'})
        g, ai = game_session_manager.reset_ai_game(uid, difficulty=difficulty)
        return jsonify(_state_payload(g, ai))

    @app.route('/api/ai/move', methods=['POST'])
    def ai_move():
        g, ai, err = _user_ai_game()
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
        if g.game_over:
            return jsonify({'success': False, 'message': '游戏已结束'})
        if g.current_turn != PLAYER_COLOR:
            return jsonify({'success': False, 'message': '请等待 AI 走棋'})

        player_result = g.make_move(from_x, from_y, to_x, to_y)
        if not player_result.get('success'):
            return jsonify(player_result)

        # Log player move
        player_move_desc = player_result.get('move_description')
        log_game_event(logger, 'PLAYER_MOVE', user_id=uid, game_mode='ai',
                       move=player_move_desc, captured=player_result.get('captured') is not None)

        ai_result = _ai_take_turn(g, ai, user_id=uid)
        ai_move_desc = None
        if ai_result and ai_result.get('success'):
            ai_move_desc = ai_result.get('ai_move') or ai_result.get('move_description')

        status_msg = (ai_result or {}).get('message') or player_result.get('message')
        check_flag = bool((ai_result or {}).get('check') or player_result.get('check'))
        checkmate_flag = bool((ai_result or {}).get('checkmate') or player_result.get('checkmate'))

        return jsonify({
            'success': True,
            'board': g.board,
            'current_turn': g.current_turn,
            'game_over': g.game_over,
            'winner': g.winner,
            'move_history': g.move_history,
            'player_move': player_move_desc,
            'ai_move': ai_move_desc,
            'message': status_msg or None,
            'check': check_flag,
            'checkmate': checkmate_flag,
        })

    @app.route('/api/ai/valid_moves', methods=['POST'])
    def ai_valid_moves():
        g, ai, err = _user_ai_game()
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
        if g.get_piece_color(piece) != PLAYER_COLOR:
            return jsonify({'success': False, 'message': '只能移动红方棋子'})
        if g.current_turn != PLAYER_COLOR:
            return jsonify({'success': False, 'message': '请等待 AI 走棋'})
        if g.game_over:
            return jsonify({'success': False, 'message': '游戏已结束'})

        moves = []
        for ty in range(10):
            for tx in range(9):
                if g.is_valid_move(x, y, tx, ty):
                    moves.append({'x': tx, 'y': ty})

        return jsonify({'success': True, 'moves': moves})

    @app.route('/api/ai/undo', methods=['POST'])
    def ai_undo():
        g, ai, err = _user_ai_game()
        if err:
            return err
        if not g.move_history:
            return jsonify({'success': False, 'message': '没有可撤销的走法'})

        last = g.move_history[-1]
        last_color = 'red' if last['piece'].startswith('red_') else 'black'
        g.undo()
        if last_color == AI_COLOR and g.move_history:
            g.undo()

        return jsonify({
            'success': True,
            'board': g.board,
            'current_turn': g.current_turn,
            'game_over': g.game_over,
            'winner': g.winner,
            'move_history': g.move_history,
        })

    @app.route('/api/ai/resign', methods=['POST'])
    def ai_resign():
        g, ai, err = _user_ai_game()
        if err:
            return err
        if g.game_over:
            return jsonify({'success': False, 'message': '游戏已结束'})
        g.game_over = True
        g.winner = AI_COLOR
        return jsonify({
            'success': True,
            'game_over': True,
            'winner': g.winner,
            'board': g.board,
            'current_turn': g.current_turn,
        })

    @app.route('/api/ai/flip', methods=['POST'])
    def ai_flip():
        g, ai, err = _user_ai_game()
        if err:
            return err
        return jsonify(g.flip())

    @app.route('/api/ai/draw', methods=['POST'])
    def ai_draw():
        g, ai, err = _user_ai_game()
        if err:
            return err
        if g.game_over:
            return jsonify({'success': False, 'message': '游戏已结束'})
        if g.current_turn != PLAYER_COLOR:
            return jsonify({'success': False, 'message': '请等待 AI 走棋'})
        if g.draw_requested_by:
            return jsonify({'success': False, 'message': '已经请求过求和'})
        g.draw_requested_by = PLAYER_COLOR
        return jsonify({
            'success': True,
            'message': '已请求求和，等待 AI 回应',
            'draw_requested_by': g.draw_requested_by
        })

    @app.route('/api/ai/analyze', methods=['POST'])
    def ai_analyze():
        g, ai, err = _user_ai_game()
        if err:
            return err
        if g.game_over:
            return jsonify({'success': False, 'message': '游戏已结束'})
        if g.current_turn != PLAYER_COLOR:
            return jsonify({'success': False, 'message': '请等待 AI 走棋'})
        
        import time
        start_time = time.time()
        move = ai.choose_move(g.board, PLAYER_COLOR)
        duration_ms = int((time.time() - start_time) * 1000)
        
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
            'evaluation': ai._evaluate(g.board),
            'duration_ms': duration_ms
        })

    @app.route('/api/ai/review', methods=['POST'])
    def ai_review():
        g, ai, err = _user_ai_game()
        if err:
            return err
        
        from game.ai import ChessAI
        review_ai = ChessAI(color='red', difficulty='hard')
        
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
            before_score = review_ai._evaluate(sim.board)
            
            best_move = review_ai.choose_move(sim.board, color)
            best_score = -float('inf')
            if best_move:
                sim2 = ChessGame()
                sim2.board = [row[:] for row in sim.board]
                sim2.board[best_move[3]][best_move[2]] = sim2.board[best_move[1]][best_move[0]]
                sim2.board[best_move[1]][best_move[0]] = None
                best_score = review_ai._evaluate(sim2.board)
            
            sim.make_move(fx, fy, tx, ty)
            after_score = review_ai._evaluate(sim.board)
            
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
    
    col_from = col_names[fx]
    col_to = col_names[tx]
    row_from = row_names_red[9 - fy]
    row_to = row_names_red[9 - ty]
    
    return f'{piece_name}{col_from}{row_from}→{col_to}{row_to}'
