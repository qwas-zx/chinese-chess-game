"""
Chinese Chess Game - Lightweight AI Engine

Strategy: Minimax with Alpha-Beta pruning + piece-value evaluation.
Pure Python, no external dependencies.

Difficulty maps to search depth:
    easy   -> depth 1 (greedy, with occasional randomness so it is beatable)
    normal -> depth 2
    hard   -> depth 3

Design notes:
- The AI reuses ``ChessGame`` only for move generation / validation. It never
  mutates the real game state — search works on deep-copied boards.
- At the root (the move the AI actually plays) full legal moves are generated
  (``check_king_safety=True``) so the AI never plays an illegal move.
- Inside the recursive search, pseudo-legal moves (``check_king_safety=False``)
  are used for speed. This is safe because the evaluation function assigns the
  king a very large value, so any line that allows the king to be captured
  scores extremely poorly and is naturally avoided.
"""
import random
from copy import deepcopy

from .core import ChessGame

# Absolute piece values (same magnitude for both colors).
PIECE_VALUES = {
    '帅': 10000, '将': 10000,
    '車': 900,
    '炮': 450,
    '马': 400,
    '相': 200, '象': 200,
    '仕': 200, '士': 200,
    '兵': 100, '卒': 100,
}

# Search depth per difficulty level.
DIFFICULTY_DEPTH = {
    'easy': 1,
    'normal': 2,
    'hard': 3,
}

# Bonus for a pawn/soldier that has crossed the river.
CROSS_RIVER_BONUS = 50

# Score returned when a side has no legal moves (effectively checkmated).
NO_MOVE_SCORE = 100000


class ChessAI:
    """Lightweight Chinese Chess AI (Minimax + Alpha-Beta)."""

    def __init__(self, color='black', difficulty='normal'):
        if color not in ('red', 'black'):
            raise ValueError("color must be 'red' or 'black'")
        if difficulty not in DIFFICULTY_DEPTH:
            raise ValueError(f"difficulty must be one of {list(DIFFICULTY_DEPTH)}")
        self.color = color
        self.set_difficulty(difficulty)
        self._sim = ChessGame()

    def set_difficulty(self, difficulty):
        if difficulty not in DIFFICULTY_DEPTH:
            raise ValueError(f"difficulty must be one of {list(DIFFICULTY_DEPTH)}")
        self.difficulty = difficulty
        self.depth = DIFFICULTY_DEPTH[difficulty]

    # ========== Public API ==========

    def choose_move(self, board, current_turn):
        legal = self._legal_moves(board, current_turn, check_king_safety=True)
        if not legal:
            return None

        if self.difficulty == 'easy' and random.random() < 0.35:
            return random.choice(legal)

        legal.sort(key=lambda m: self._capture_value(board, m), reverse=True)

        best_move = legal[0]
        alpha, beta = -float('inf'), float('inf')
        maximizing = current_turn == self.color

        if maximizing:
            best_score = -float('inf')
            for move in legal:
                score = self._minimax(self._apply(board, move), self.depth - 1,
                                      alpha, beta, self._opponent(current_turn))
                if score > best_score:
                    best_score = score
                    best_move = move
                alpha = max(alpha, best_score)
                if beta <= alpha:
                    break
        else:
            best_score = float('inf')
            for move in legal:
                score = self._minimax(self._apply(board, move), self.depth - 1,
                                      alpha, beta, self._opponent(current_turn))
                if score < best_score:
                    best_score = score
                    best_move = move
                beta = min(beta, best_score)
                if beta <= alpha:
                    break

        return best_move

    # ========== Search ==========

    def _minimax(self, board, depth, alpha, beta, current_turn):
        if depth == 0 or self._is_terminal(board):
            return self._evaluate(board)

        moves = self._legal_moves(board, current_turn, check_king_safety=False)
        if not moves:
            return -NO_MOVE_SCORE if current_turn == self.color else NO_MOVE_SCORE

        moves.sort(key=lambda m: self._capture_value(board, m), reverse=True)
        maximizing = current_turn == self.color

        if maximizing:
            best = -float('inf')
            for move in moves:
                score = self._minimax(self._apply(board, move), depth - 1,
                                      alpha, beta, self._opponent(current_turn))
                if score > best:
                    best = score
                if best > alpha:
                    alpha = best
                if beta <= alpha:
                    break
            return best
        else:
            best = float('inf')
            for move in moves:
                score = self._minimax(self._apply(board, move), depth - 1,
                                      alpha, beta, self._opponent(current_turn))
                if score < best:
                    best = score
                if best < beta:
                    beta = best
                if beta <= alpha:
                    break
            return best

    # ========== Helpers ==========

    @staticmethod
    def _opponent(color):
        return 'black' if color == 'red' else 'red'

    def _legal_moves(self, board, color, check_king_safety):
        self._sim.board = deepcopy(board)
        self._sim.current_turn = color
        moves = []
        for y in range(10):
            row = board[y]
            for x in range(9):
                piece = row[x]
                if piece is None:
                    continue
                if self._sim.get_piece_color(piece) != color:
                    continue
                for ty in range(10):
                    for tx in range(9):
                        if self._sim.is_valid_move(x, y, tx, ty,
                                                   color_override=color,
                                                   check_king_safety=check_king_safety):
                            moves.append((x, y, tx, ty))
        return moves

    @staticmethod
    def _apply(board, move):
        fx, fy, tx, ty = move
        nb = deepcopy(board)
        nb[ty][tx] = nb[fy][fx]
        nb[fy][fx] = None
        return nb

    @staticmethod
    def _capture_value(board, move):
        _, _, tx, ty = move
        target = board[ty][tx]
        if target is None:
            return 0
        return PIECE_VALUES.get(target.split('_')[1], 0)

    @staticmethod
    def _is_terminal(board):
        has_red_king = False
        has_black_king = False
        for row in board:
            for piece in row:
                if piece == 'red_帅':
                    has_red_king = True
                elif piece == 'black_将':
                    has_black_king = True
        return not (has_red_king and has_black_king)

    def _evaluate(self, board):
        score = 0
        for y in range(10):
            row = board[y]
            for x in range(9):
                piece = row[x]
                if piece is None:
                    continue
                color = 'red' if piece.startswith('red_') else 'black'
                ptype = piece.split('_')[1]
                value = PIECE_VALUES.get(ptype, 0)
                if ptype in ('兵', '卒'):
                    if color == 'red' and y <= 4:
                        value += CROSS_RIVER_BONUS
                    elif color == 'black' and y >= 5:
                        value += CROSS_RIVER_BONUS
                if color == self.color:
                    score += value
                else:
                    score -= value
        return score
