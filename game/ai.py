"""
Chinese Chess Game - Advanced AI Engine

Strategy: Minimax with Alpha-Beta pruning + advanced enhancements:
- Piece-Square Tables (PST): Positional evaluation
- Killer Moves Heuristic: Remember good moves for later
- History Heuristic: Track move performance
- Iterative Deepening: Progressive search depth
- Time Control: Limit thinking time
- Opening Book: Common opening moves
- Transposition Table: Cache evaluated positions
- Null Move Pruning: Skip weak opponent moves

Difficulty maps to search depth and time:
    easy   -> depth 1-2, time 0.5s, randomness 35%
    normal -> depth 3-4, time 2s
    hard   -> depth 4-5, time 5s

Author: Enhanced version for production use
"""
import logging
import random
import time
import hashlib
from copy import deepcopy
from typing import List, Tuple, Dict, Optional

from .core import ChessGame

logger = logging.getLogger(__name__)


# ========== Piece Values ==========
PIECE_VALUES = {
    '帅': 10000, '将': 10000,
    '車': 900,
    '炮': 450,
    '马': 400,
    '相': 200, '象': 200,
    '仕': 200, '士': 200,
    '兵': 100, '卒': 100,
}

# ========== Piece-Square Tables (PST) ==========
# Bonus/malus based on piece position
# Red perspective (flip for black)

# 10 rows x 9 cols
PST = {
    '帅': [  # King - stay in palace, center is better
        [0,  0,  0, -10, -15, -10, 0,  0,  0],
        [0,  0,  0, -5,  -10, -5,  0,  0,  0],
        [0,  0,  0,  0,   0,   0,  0,  0,  0],
        [0]*9,
        [0]*9,
        [0]*9,
        [0]*9,
        [0,  0,  0,  0,   0,   0,  0,  0,  0],
        [0,  0,  0, -5,  -10, -5,  0,  0,  0],
        [0,  0,  0, -10, -15, -10, 0,  0,  0],
    ],
    '车': [  # Rook - control open files, rank 0/9
        [-10, -8, -6, -4, 0, -4, -6, -8, -10],
        [-8,  -6, -4, -2, 0, -2, -4, -6, -8],
        [-6,  -4, -2,  0,  2,  0, -2, -4, -6],
        [-4,  -2,  0,  2,  4,  2,  0, -2, -4],
        [-2,   0,  2,  4,  6,  4,  2,  0, -2],
        [-4,  -2,  0,  2,  4,  2,  0, -2, -4],
        [-6,  -4, -2,  0,  2,  0, -2, -4, -6],
        [-8,  -6, -4, -2, 0, -2, -4, -6, -8],
        [-10, -8, -6, -4, 0, -4, -6, -8, -10],
        [-10, -8, -6, -4, 0, -4, -6, -8, -10],
    ],
    '马': [  # Horse - avoid edges, center is good
        [-20, -15, -10, -5, 0, -5, -10, -15, -20],
        [-15, -10, -5,  0,  5,  0, -5,  -10, -15],
        [-10, -5,  0,   5,  10, 5,  0,  -5,  -10],
        [-5,   0,  5,   10, 15, 10, 5,   0,  -5],
        [0,    5,  10,  15, 20, 15, 10,  5,   0],
        [-5,   0,  5,   10, 15, 10, 5,   0,  -5],
        [-10, -5,  0,   5,  10, 5,  0,  -5,  -10],
        [-15, -10, -5,  0,  5,  0, -5,  -10, -15],
        [-20, -15, -10, -5, 0, -5, -10, -15, -20],
        [-20, -15, -10, -5, 0, -5, -10, -15, -20],
    ],
    '炮': [  # Cannon - better in center, needs screen
        [-5,  -3, -1,  0,  2,  0, -1, -3, -5],
        [-3,  -1,  1,  3,  5,  3,  1, -1, -3],
        [-1,   1,  3,  5,  7,  5,  3,  1, -1],
        [0,    3,  5,  7,  9,  7,  5,  3,  0],
        [2,    5,  7,  9,  11, 9,  7,  5,  2],
        [0,    3,  5,  7,  9,  7,  5,  3,  0],
        [-1,   1,  3,  5,  7,  5,  3,  1, -1],
        [-3,  -1,  1,  3,  5,  3,  1, -1, -3],
        [-5,  -3, -1,  0,  2,  0, -1, -3, -5],
        [-5,  -3, -1,  0,  2,  0, -1, -3, -5],
    ],
    '相': [  # Elephant - stay in own half, protect king
        [0,   0,  0, -10, -10, -10, 0,  0,  0],
        [0,   0,  0, -5,  -5,  -5,  0,  0,  0],
        [0,   0,  0,  0,   0,   0,  0,  0,  0],
        [-10, -5, 0,  5,   10,  5,  0, -5, -10],
        [-10, -5, 0,  10,  15,  10, 0, -5, -10],
        [-10, -5, 0,  5,   10,  5,  0, -5, -10],
        [0,   0,  0,  0,   0,   0,  0,  0,  0],
        [0,   0,  0, -5,  -5,  -5,  0,  0,  0],
        [0,   0,  0, -10, -10, -10, 0,  0,  0],
        [0,   0,  0, -10, -10, -10, 0,  0,  0],
    ],
    '仕': [  # Advisor - stay in palace
        [0,   0,  0, -5, -10, -5,  0,  0,  0],
        [0,   0,  0,  0, -5,  0,  0,  0,  0],
        [0,   0,  0,  0,  0,  0,  0,  0,  0],
        [0]*9,
        [0]*9,
        [0]*9,
        [0]*9,
        [0,   0,  0,  0,  0,  0,  0,  0,  0],
        [0,   0,  0,  0, -5,  0,  0,  0,  0],
        [0,   0,  0, -5, -10, -5,  0,  0,  0],
    ],
    '兵': [  # Pawn - advance is good, cross river is great
        [-10, -10, -10, -5,  0, -5, -10, -10, -10],
        [-10, -10, -10, -5,  5, -5, -10, -10, -10],
        [-5,  -5,  -5,  0,  10, 0,  -5,  -5,  -5],
        [0,    0,   5,  10, 20, 10,  5,   0,   0],
        [5,    10,  15, 20, 30, 20, 15,  10,  5],
        [10,   15,  20, 25, 35, 25, 20,  15, 10],
        [15,   20,  25, 30, 40, 30, 25,  20, 15],
        [20,   25,  30, 35, 45, 35, 30,  25, 20],
        [25,   30,  35, 40, 50, 40, 35,  30, 25],
        [30,   35,  40, 45, 55, 45, 40,  35, 30],
    ],
}

# Difficulty configuration
DIFFICULTY_CONFIG = {
    'easy': {
        'depth': 2,
        'time_limit': 0.5,
        'randomness': 0.35,
        'use_book': False,
        'use_null_move': False,
    },
    'normal': {
        'depth': 4,
        'time_limit': 2.0,
        'randomness': 0.0,
        'use_book': True,
        'use_null_move': True,
    },
    'hard': {
        'depth': 5,
        'time_limit': 5.0,
        'randomness': 0.0,
        'use_book': True,
        'use_null_move': True,
    },
}

NO_MOVE_SCORE = 100000

MOBILITY_WEIGHT = 8
KING_SAFETY_WEIGHT = 180
THREAT_WEIGHT = 45
DEFENDED_PIECE_WEIGHT = 20
CENTER_CONTROL_WEIGHT = 6


class TranspositionTable:
    """Cache for evaluated positions to avoid redundant computation."""

    def __init__(self, max_size: int = 100000):
        self.table: Dict[str, Tuple[int, int, Optional[Tuple]]] = {}
        self.max_size = max_size

    def _hash_board(self, board) -> str:
        """Generate a hash key for the board position."""
        h = hashlib.md5()
        for row in board:
            for piece in row:
                h.update((piece or '.').encode())
        return h.hexdigest()

    def get(self, board, depth: int) -> Optional[Tuple[int, int, Optional[Tuple]]]:
        """Get cached evaluation if depth is sufficient."""
        key = self._hash_board(board)
        entry = self.table.get(key)
        if entry and entry[0] >= depth:
            return entry
        return None

    def put(self, board, depth: int, score: int, best_move: Optional[Tuple] = None):
        """Store evaluation in cache."""
        if len(self.table) >= self.max_size:
            # Simple eviction: clear half randomly
            keys_to_remove = random.sample(list(self.table.keys()), self.max_size // 2)
            for k in keys_to_remove:
                del self.table[k]
        key = self._hash_board(board)
        self.table[key] = (depth, score, best_move)

    def clear(self):
        """Clear the transposition table."""
        self.table.clear()


class OpeningBook:
    """Common opening moves for faster play and better opening."""

    def __init__(self):
        # Simple opening book: (from_x, from_y, to_x, to_y) for red at start
        # These are standard openings
        self.book = {
            # Central cannon opening
            'central_cannon': [(4, 9, 4, 7)],
            # Horse opening
            'horse': [(1, 9, 2, 7), (7, 9, 6, 7)],
            # Rook opening
            'rook': [(0, 9, 0, 7), (8, 9, 8, 7)],
        }

    def get_opening_move(self, board, move_count: int, color: str) -> Optional[Tuple[int, int, int, int]]:
        """Get a book move if in opening phase."""
        if move_count > 6:  # Only use book for first 3 moves each
            return None

        # Simple heuristic: prefer center cannon on first move
        if move_count == 0 and color == 'red':
            # Check if central cannon is available
            if board[9][4] == 'red_炮':
                return (4, 9, 4, 7)

        return None


class ChessAI:
    """Advanced Chinese Chess AI with multiple enhancements."""

    def __init__(self, color: str = 'black', difficulty: str = 'normal'):
        if color not in ('red', 'black'):
            raise ValueError("color must be 'red' or 'black'")
        if difficulty not in DIFFICULTY_CONFIG:
            raise ValueError(f"difficulty must be one of {list(DIFFICULTY_CONFIG)}")

        self.color = color
        self.set_difficulty(difficulty)
        self._sim = ChessGame()

        # Enhancement components
        self.transposition_table = TranspositionTable()
        self.opening_book = OpeningBook()
        self.killer_moves: Dict[int, List[Tuple]] = {}  # depth -> [moves]
        self.history_table: Dict[Tuple, int] = {}  # move -> score

        # Statistics
        self.nodes_searched = 0
        self.cache_hits = 0

    def set_difficulty(self, difficulty: str):
        """Set AI difficulty level."""
        if difficulty not in DIFFICULTY_CONFIG:
            raise ValueError(f"difficulty must be one of {list(DIFFICULTY_CONFIG)}")
        self.difficulty = difficulty
        config = DIFFICULTY_CONFIG[difficulty]
        self.max_depth = config['depth']
        self.time_limit = config['time_limit']
        self.randomness = config['randomness']
        self.use_book = config['use_book']
        self.use_null_move = config['use_null_move']

    # ========== Public API ==========

    def choose_move(self, board, current_turn: str) -> Optional[Tuple[int, int, int, int]]:
        """Choose the best move for the current position."""
        self.nodes_searched = 0
        self.cache_hits = 0
        start_time = time.time()

        legal = self._legal_moves(board, current_turn, check_king_safety=True)
        if not legal:
            return None

        # Random move in easy mode
        if self.randomness > 0 and random.random() < self.randomness:
            move = random.choice(legal)
            logger.debug(f"AI random move: {move}")
            return move

        tactical_move = self._select_tactical_move(board, legal, current_turn)
        if tactical_move is not None:
            logger.debug(f"AI tactical move: {tactical_move}")
            return tactical_move

        # Check opening book
        if self.use_book:
            move_count = self._count_moves(board)
            book_move = self.opening_book.get_opening_move(board, move_count, current_turn)
            if book_move and self._is_legal(board, book_move, current_turn):
                logger.debug(f"AI book move: {book_move}")
                return book_move

        # Iterative deepening
        best_move = legal[0]
        best_score = -float('inf')

        for depth in range(1, self.max_depth + 1):
            if time.time() - start_time > self.time_limit * 0.8:
                break  # Time running out

            move, score = self._search_root(board, depth, current_turn, start_time)

            if move is not None:
                best_move = move
                best_score = score

            logger.debug(f"Iterative deepening depth={depth}, move={best_move}, score={best_score}")

        # Clear killer moves for next search
        self.killer_moves.clear()

        elapsed_ms = int((time.time() - start_time) * 1000)
        logger.info(f"AI move: {best_move}, score={best_score}, depth={depth}, "
                    f"nodes={self.nodes_searched}, cache_hits={self.cache_hits}, time={elapsed_ms}ms")

        return best_move

    def _select_tactical_move(self, board, legal, current_turn):
        """Prefer immediate tactical moves such as captures and checks."""
        scored = []
        for move in legal:
            fx, fy, tx, ty = move
            piece = board[fy][fx]
            target = board[ty][tx]
            if piece is None:
                continue

            score = 0
            if target is not None:
                score += PIECE_VALUES.get(ChessGame.get_piece_type(target), 0) * 20
                if not self._is_square_attacked(board, tx, ty, self._opponent(ChessGame.get_piece_color(piece))):
                    score += 800

            if self._results_in_check(board, move, self._opponent(ChessGame.get_piece_color(piece))):
                score += 1500

            if score > 0:
                scored.append((score, move))

        if not scored:
            return None
        scored.sort(reverse=True, key=lambda item: item[0])
        return scored[0][1]

    def _search_root(self, board, depth: int, current_turn: str, start_time: float):
        """Search at root level with move ordering."""
        legal = self._legal_moves(board, current_turn, check_king_safety=True)
        if not legal:
            return None, -NO_MOVE_SCORE

        # Move ordering
        legal = self._order_moves(board, legal, depth)

        best_move = legal[0]
        best_score = -float('inf')
        alpha, beta = -float('inf'), float('inf')

        for move in legal:
            if time.time() - start_time > self.time_limit:
                break

            new_board = self._apply(board, move)
            score = -self._minimax(new_board, depth - 1, -beta, -alpha,
                                   self._opponent(current_turn), start_time)

            if score > best_score:
                best_score = score
                best_move = move

            alpha = max(alpha, score)
            self._update_history(move, depth, score)

        return best_move, best_score

    # ========== Search ==========

    def _minimax(self, board, depth: int, alpha: float, beta: float,
                 current_turn: str, start_time: float) -> int:
        """Negamax with alpha-beta pruning and enhancements."""
        self.nodes_searched += 1

        # Time check
        if time.time() - start_time > self.time_limit:
            return 0

        # Terminal depth
        if self._is_terminal(board):
            return self._evaluate(board)

        effective_depth = depth
        if depth > 0 and self._is_tactical_position(board, current_turn):
            effective_depth = depth + 1

        if effective_depth <= 0:
            return self._evaluate(board)

        # Transposition table lookup
        cached = self.transposition_table.get(board, effective_depth)
        if cached:
            self.cache_hits += 1
            return cached[1]

        # Null move pruning (skip opponent's weak move)
        if self.use_null_move and effective_depth >= 2 and current_turn != self.color:
            null_score = -self._minimax(board, effective_depth - 2, -beta, -beta + 1,
                                        self._opponent(current_turn), start_time)
            if null_score >= beta:
                return beta  # Prune

        # Generate moves
        moves = self._legal_moves(board, current_turn, check_king_safety=False)
        if not moves:
            return -NO_MOVE_SCORE if current_turn == self.color else NO_MOVE_SCORE

        # Move ordering
        moves = self._order_moves(board, moves, effective_depth)

        best_score = -float('inf')
        best_move = None

        for move in moves:
            new_board = self._apply(board, move)
            score = -self._minimax(new_board, depth - 1, -beta, -alpha,
                                   self._opponent(current_turn), start_time)

            if score > best_score:
                best_score = score
                best_move = move

            alpha = max(alpha, score)
            if alpha >= beta:
                self._store_killer(move, effective_depth)
                break  # Beta cutoff

        # Store in transposition table
        self.transposition_table.put(board, effective_depth, best_score, best_move)

        return best_score

    # ========== Move Ordering ==========

    def _order_moves(self, board, moves: List[Tuple], depth: int) -> List[Tuple]:
        """Order moves to improve alpha-beta efficiency."""
        scored_moves = []

        for move in moves:
            score = 0
            fx, fy, tx, ty = move
            target = board[ty][tx]
            piece = board[fy][fx]
            piece_type = ChessGame.get_piece_type(piece)

            # Captures are good
            if target:
                score += PIECE_VALUES.get(ChessGame.get_piece_type(target), 0) * 10

            # Hanging-piece captures are especially strong
            if target:
                opponent_color = self._opponent(ChessGame.get_piece_color(piece))
                if not self._is_square_attacked(board, tx, ty, opponent_color):
                    score += 800

            # Checks are excellent tactical moves
            if self._results_in_check(board, move, self._opponent(ChessGame.get_piece_color(piece))):
                score += 300

            # Good if it attacks a high-value target
            if target and PIECE_VALUES.get(piece_type, 0) < PIECE_VALUES.get(ChessGame.get_piece_type(target), 0):
                score += 80

            # Killer moves
            if depth in self.killer_moves and move in self.killer_moves[depth]:
                score += 500

            # History heuristic
            if move in self.history_table:
                score += self.history_table[move]

            # Centralization / development bias
            score += self._positional_move_bonus(board, move, piece_type)

            scored_moves.append((score, move))

        # Sort by score descending
        scored_moves.sort(reverse=True, key=lambda x: x[0])
        return [m for _, m in scored_moves]

    def _store_killer(self, move: Tuple, depth: int):
        """Store a killer move for this depth."""
        if depth not in self.killer_moves:
            self.killer_moves[depth] = []
        if len(self.killer_moves[depth]) < 2 and move not in self.killer_moves[depth]:
            self.killer_moves[depth].append(move)

    def _update_history(self, move: Tuple, depth: int, score: int):
        """Update history heuristic table."""
        if move not in self.history_table:
            self.history_table[move] = 0
        self.history_table[move] += depth * depth

    # ========== Evaluation ==========

    def _evaluate(self, board) -> int:
        """Evaluate board position from AI's perspective."""
        score = 0

        for y in range(10):
            for x in range(9):
                piece = board[y][x]
                if piece is None:
                    continue

                color = ChessGame.get_piece_color(piece)
                ptype = ChessGame.get_piece_type(piece)

                value = PIECE_VALUES.get(ptype, 0)

                if ptype in PST:
                    pst = PST[ptype]
                    if color == 'red':
                        pos_value = pst[y][x]
                    else:
                        pos_value = pst[9 - y][x]
                    value += pos_value

                value += self._piece_activity_bonus(board, x, y, color, ptype)

                if self._is_square_defended(board, x, y, color):
                    value += DEFENDED_PIECE_WEIGHT
                else:
                    value -= 25

                if color == self.color:
                    score += value
                else:
                    score -= value

        score += self._mobility_bonus(board, self.color) - self._mobility_bonus(board, self._opponent(self.color))
        score += self._king_safety_bonus(board, self.color) - self._king_safety_bonus(board, self._opponent(self.color))
        score += self._threat_bonus(board, self.color) - self._threat_bonus(board, self._opponent(self.color))
        return score

    def _piece_activity_bonus(self, board, x, y, color, ptype) -> int:
        """Small positional bonus for activity and centralization."""
        bonus = 0
        if ptype in ('车', '马', '炮'):
            center_distance = abs(x - 4) + abs(y - 4)
            bonus += max(0, 8 - center_distance) * CENTER_CONTROL_WEIGHT
        if ptype in ('兵', '卒'):
            if color == 'red':
                bonus += max(0, 5 - y) * 2
            else:
                bonus += max(0, y - 4) * 2
        if ptype in ('帅', '将'):
            bonus += max(0, 8 - abs(x - 4)) * 3
        return bonus

    def _positional_move_bonus(self, board, move, ptype) -> int:
        fx, fy, tx, ty = move
        bonus = 0
        if ptype in ('车', '马', '炮'):
            bonus += max(0, 4 - abs(tx - 4)) * 2
        if ptype in ('兵', '卒'):
            bonus += 2 if tx == 4 else 0
        if ptype in ('帅', '将'):
            bonus += 6 if (3 <= tx <= 5 and 0 <= ty <= 2) or (3 <= tx <= 5 and 7 <= ty <= 9) else 0
        return bonus

    def _mobility_bonus(self, board, color) -> int:
        moves = self._legal_moves(board, color, check_king_safety=False)
        return len(moves) * MOBILITY_WEIGHT

    def _king_safety_bonus(self, board, color) -> int:
        king_pos = self._find_king_position(board, color)
        if king_pos is None:
            return -100000
        x, y = king_pos
        safety = 0
        if self._is_square_attacked(board, x, y, self._opponent(color)):
            safety -= KING_SAFETY_WEIGHT
        else:
            safety += 30
        return safety

    def _threat_bonus(self, board, color) -> int:
        moves = self._legal_moves(board, color, check_king_safety=False)
        threats = 0
        for move in moves:
            fx, fy, tx, ty = move
            target = board[ty][tx]
            if target is not None:
                threats += PIECE_VALUES.get(ChessGame.get_piece_type(target), 0) // 100
        return threats * THREAT_WEIGHT

    def _is_square_defended(self, board, x, y, color) -> bool:
        return self._is_square_attacked(board, x, y, color)

    def _is_square_attacked(self, board, x, y, color) -> bool:
        for oy in range(10):
            for ox in range(9):
                piece = board[oy][ox]
                if piece is None:
                    continue
                if ChessGame.get_piece_color(piece) != color:
                    continue
                if self._sim.is_valid_move(ox, oy, x, y, board=board, color_override=color, check_king_safety=False):
                    return True
        return False

    def _results_in_check(self, board, move, color) -> bool:
        fx, fy, tx, ty = move
        piece = board[fy][fx]
        if piece is None:
            return False
        new_board = deepcopy(board)
        new_board[ty][tx] = new_board[fy][fx]
        new_board[fy][fx] = None
        self._sim.board = new_board
        self._sim.current_turn = color
        return self._sim.is_in_check(color, new_board)

    def _is_tactical_position(self, board, color) -> bool:
        if self._sim.is_in_check(color, board):
            return True
        for move in self._legal_moves(board, color, check_king_safety=False):
            fx, fy, tx, ty = move
            target = board[ty][tx]
            if target is not None:
                return True
        return False

    def _find_king_position(self, board, color):
        king_piece = 'red_帅' if color == 'red' else 'black_将'
        for y, row in enumerate(board):
            for x, piece in enumerate(row):
                if piece == king_piece:
                    return x, y
        return None

    # ========== Helpers ==========

    @staticmethod
    def _opponent(color: str) -> str:
        return 'black' if color == 'red' else 'red'

    def _legal_moves(self, board, color: str, check_king_safety: bool) -> List[Tuple]:
        """Generate all legal moves for a color."""
        self._sim.board = deepcopy(board)
        self._sim.current_turn = color
        moves = []

        for y in range(10):
            for x in range(9):
                piece = board[y][x]
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

    def _is_legal(self, board, move: Tuple, color: str) -> bool:
        """Check if a specific move is legal."""
        fx, fy, tx, ty = move
        self._sim.board = deepcopy(board)
        self._sim.current_turn = color
        return self._sim.is_valid_move(fx, fy, tx, ty,
                                        color_override=color,
                                        check_king_safety=True)

    @staticmethod
    def _apply(board, move: Tuple):
        """Apply move and return new board."""
        fx, fy, tx, ty = move
        nb = deepcopy(board)
        nb[ty][tx] = nb[fy][fx]
        nb[fy][fx] = None
        return nb

    @staticmethod
    def _is_terminal(board) -> bool:
        """Check if game is over (king captured)."""
        has_red_king = False
        has_black_king = False
        for row in board:
            for piece in row:
                if piece == 'red_帅':
                    has_red_king = True
                elif piece == 'black_将':
                    has_black_king = True
        return not (has_red_king and has_black_king)

    def _count_moves(self, board) -> int:
        """Estimate move count based on board development."""
        count = 0
        for y in range(10):
            for x in range(9):
                piece = board[y][x]
                if piece:
                    ptype = piece.split('_')[1]
                    # Assume opening moves if pieces are in starting positions
                    if ptype in ('马', '炮', '车'):
                        if (piece.startswith('red_') and y >= 7) or \
                           (piece.startswith('black_') and y <= 2):
                            count += 1
        return count