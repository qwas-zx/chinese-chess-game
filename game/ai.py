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
    '帅': [  # King - safest deep in own palace, center column best
        # The previous table gave the back-center palace square (where the
        # king starts and is safest) a -15 penalty and the exposed front of
        # the palace a 0 bonus -- i.e. it rewarded walking the king forward.
        # Inverted so the king is rewarded for tucking back and penalized
        # for moving to the front of the palace.
        [0, 0, 0,  8, 12,  8, 0, 0, 0],   # y=0 black back palace (king start)
        [0, 0, 0,  4,  6,  4, 0, 0, 0],
        [0, 0, 0, -4, -6, -4, 0, 0, 0],   # y=2 black front palace (exposed)
        [0]*9,
        [0]*9,
        [0]*9,
        [0]*9,
        [0, 0, 0, -4, -6, -4, 0, 0, 0],   # y=7 red front palace (exposed)
        [0, 0, 0,  4,  6,  4, 0, 0, 0],
        [0, 0, 0,  8, 12,  8, 0, 0, 0],   # y=9 red back palace (king start)
    ],
    '車': [  # Rook - control open files, rank 0/9 (uses traditional char to match piece type)
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
        # Indexed [y][x] from red's perspective. Red pawns start at y=6 and
        # advance toward y=0, so the table must REWARD low y for red. The
        # previous version was flipped vertically, giving red pawns +40 for
        # sitting on their start square and 0 for reaching the back rank --
        # i.e. it punished advancing. For black (卒) the evaluator reads
        # pst[9-y][x], which mirrors this table, so black pawns are rewarded
        # for advancing toward y=9 the same way.
        [30,   35,  40, 45, 55, 45, 40,  35, 30],   # y=0 deep in enemy territory
        [25,   30,  35, 40, 50, 40, 35,  30, 25],
        [20,   25,  30, 35, 45, 35, 30,  25, 20],
        [15,   20,  25, 30, 40, 30, 25,  20, 15],   # crossed the river
        [10,   15,  20, 25, 35, 25, 20,  15, 10],
        [5,    10,  15, 20, 30, 20, 15,  10,  5],   # own side, pre-river
        [0,    0,   5,  10, 20, 10, 5,   0,   0],   # y=6 red pawn start
        [-5,  -5,  -5,  0,  10, 0,  -5,  -5,  -5],
        [-10, -10, -10, -5,  5, -5, -10, -10, -10],
        [-10, -10, -10, -5,  0, -5, -10, -10, -10],
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

KING_SAFETY_WEIGHT = 120
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
        position_hash = self.transposition_table._hash_board(board)
        logger.debug("AI choose_move start", extra={
            'position_hash': position_hash,
            'current_turn': current_turn,
            'difficulty': self.difficulty,
            'color': self.color,
            'max_depth': self.max_depth,
            'time_limit': self.time_limit,
            'use_book': self.use_book,
            'use_null_move': self.use_null_move,
            'randomness': self.randomness,
            'legal_moves': len(legal),
        })

        if not legal:
            logger.info("AI choose_move no legal moves", extra={
                'position_hash': position_hash,
                'current_turn': current_turn,
                'difficulty': self.difficulty,
            })
            return None

        # Random move in easy mode
        if self.randomness > 0 and random.random() < self.randomness:
            move = random.choice(legal)
            logger.info("AI chose random move", extra={
                'position_hash': position_hash,
                'decision_reason': 'random',
                'selected_move': move,
                'legal_moves': len(legal),
            })
            return move

        tactical_move = self._select_tactical_move(board, legal, current_turn)
        if tactical_move is not None:
            logger.info("AI chose tactical move", extra={
                'position_hash': position_hash,
                'decision_reason': 'tactical',
                'selected_move': tactical_move,
                'legal_moves': len(legal),
            })
            return tactical_move

        # Check opening book
        if self.use_book:
            move_count = self._count_moves(board)
            book_move = self.opening_book.get_opening_move(board, move_count, current_turn)
            if book_move and self._is_legal(board, book_move, current_turn):
                logger.info("AI chose opening book move", extra={
                    'position_hash': position_hash,
                    'decision_reason': 'opening_book',
                    'selected_move': book_move,
                    'legal_moves': len(legal),
                    'book_move_count': move_count,
                })
                return book_move

        best_move = legal[0]
        best_score = -float('inf')
        actual_search_depth = 0

        for depth in range(1, self.max_depth + 1):
            if time.time() - start_time > self.time_limit * 0.8:
                logger.warning("AI iterative deepening stopped early due to time", extra={
                    'position_hash': position_hash,
                    'current_turn': current_turn,
                    'difficulty': self.difficulty,
                    'search_depth': depth - 1,
                    'elapsed_ms': int((time.time() - start_time) * 1000),
                })
                break  # Time running out

            actual_search_depth = depth
            move, score = self._search_root(board, depth, current_turn, start_time)

            if move is not None:
                best_move = move
                best_score = score

            logger.debug("AI iterative deepening iteration", extra={
                'position_hash': position_hash,
                'depth': depth,
                'move': best_move,
                'score': best_score,
                'legal_moves': len(legal),
            })

        self.killer_moves.clear()

        elapsed_ms = int((time.time() - start_time) * 1000)
        logger.info("AI choose_move summary", extra={
            'position_hash': position_hash,
            'current_turn': current_turn,
            'difficulty': self.difficulty,
            'selected_move': best_move,
            'selected_score': best_score,
            'search_depth': actual_search_depth,
            'legal_moves': len(legal),
            'nodes_searched': self.nodes_searched,
            'cache_hits': self.cache_hits,
            'search_time_ms': elapsed_ms,
            'use_book': self.use_book,
            'use_null_move': self.use_null_move,
            'randomness': self.randomness,
        })

        return best_move

    def _select_tactical_move(self, board, legal, current_turn):
        """Prefer clearly-winning tactical moves without invoking the full search.

        Conservative: only short-circuit the minimax search when there is an
        obviously winning capture available -- capturing an undefended piece,
        or a cheap attacker winning a defended but more valuable piece.
        Checks and balanced exchanges are deliberately left to the full
        search so the engine does not play them blindly. The previous
        version gave a flat +1500 bonus to any check and bypassed the search
        for every capture, which was the main source of overly aggressive
        play (e.g. sacrificing material for pointless checking sequences).
        """
        best_score = 0
        best_move = None
        for move in legal:
            fx, fy, tx, ty = move
            piece = board[fy][fx]
            target = board[ty][tx]
            if piece is None or target is None:
                continue  # non-captures are handled by the full search

            piece_color = ChessGame.get_piece_color(piece)
            if piece_color is None:
                continue

            piece_type = ChessGame.get_piece_type(piece)
            target_type = ChessGame.get_piece_type(target)
            if piece_type is None or target_type is None:
                continue

            attacker_value = PIECE_VALUES.get(piece_type, 0)
            target_value = PIECE_VALUES.get(target_type, 0)
            opponent_color = self._opponent(piece_color)

            # Free capture: target square is undefended -> clearly winning.
            if not self._is_square_attacked(board, tx, ty, opponent_color):
                score = target_value + 1000
                if score > best_score:
                    best_score = score
                    best_move = move
            # Favorable exchange: cheap attacker wins a more valuable defended piece.
            elif target_value > attacker_value + 200:
                score = (target_value - attacker_value) // 2
                if score > best_score:
                    best_score = score
                    best_move = move

        return best_move

    def _search_root(self, board, depth: int, current_turn: str, start_time: float):
        """Search at root level with move ordering."""
        legal = self._legal_moves(board, current_turn, check_king_safety=True)
        if not legal:
            logger.debug("AI root search has no legal moves", extra={'depth': depth})
            return None, -NO_MOVE_SCORE

        # Move ordering
        legal = self._order_moves(board, legal, depth)
        logger.debug("AI root search start", extra={
            'depth': depth,
            'current_turn': current_turn,
            'legal_moves': len(legal),
        })

        best_move = legal[0]
        best_score = -10**18
        alpha, beta = -10**18, 10**18

        for move in legal:
            if time.time() - start_time > self.time_limit:
                logger.warning("AI root search stopped early due to timeout", extra={
                    'depth': depth,
                    'current_turn': current_turn,
                })
                break

            new_board = self._apply(board, move)
            score = -self._minimax(new_board, depth - 1, -beta, -alpha,
                                   self._opponent(current_turn), start_time)

            if score > best_score:
                best_score = score
                best_move = move

            alpha = max(alpha, score)
            self._update_history(move, depth, score)

        logger.debug("AI root search finished", extra={
            'depth': depth,
            'best_move': best_move,
            'best_score': best_score,
            'alpha': alpha,
            'beta': beta,
        })
        return best_move, best_score

    # ========== Search ==========

    def _minimax(self, board, depth: int, alpha: float, beta: float,
                 current_turn: str, start_time: float) -> int:
        """Negamax with alpha-beta pruning and enhancements.

        The search depth is strictly bounded to avoid runaway recursion in
        tactical positions (e.g. repeated checks) and to keep the engine
        responsive under load.
        """
        self.nodes_searched += 1

        if time.time() - start_time > self.time_limit:
            return self._eval_for_turn(board, current_turn)

        if self._is_terminal(board):
            return self._eval_for_turn(board, current_turn)

        # Clamp negative or excessive depths to a safe search horizon.
        if depth <= 0:
            return self._eval_for_turn(board, current_turn)

        # Consume one ply for the current node before expanding. We keep the
        # recursion strictly monotonic so tactical loops (especially repeated
        # checks) cannot keep the search alive indefinitely.
        remaining_depth = depth - 1
        if remaining_depth < 0:
            return self._eval_for_turn(board, current_turn)

        in_check = self._sim.is_in_check(current_turn, board)
        effective_depth = remaining_depth
        if effective_depth > self.max_depth + 2:
            effective_depth = self.max_depth + 2

        if effective_depth <= 0:
            return self._eval_for_turn(board, current_turn)

        cached = self.transposition_table.get(board, effective_depth)
        if cached:
            self.cache_hits += 1
            logger.debug("transposition cache hit", extra={
                'depth': effective_depth,
                'cached_score': cached[1],
            })
            return cached[1]

        if self.use_null_move and effective_depth >= 2 and not in_check:
            null_score = -self._minimax(board, effective_depth - 2, -beta, -beta + 1,
                                        self._opponent(current_turn), start_time)
            if null_score >= beta:
                logger.debug("null move cutoff", extra={
                    'depth': effective_depth,
                    'null_score': null_score,
                    'beta': beta,
                })
                return int(beta)

        moves = self._legal_moves(board, current_turn, check_king_safety=False)
        if not moves:
            logger.debug("AI node has no legal moves", extra={'depth': effective_depth, 'current_turn': current_turn})
            return -NO_MOVE_SCORE

        moves = self._order_moves(board, moves, effective_depth)

        best_score = -10**18
        best_move = None

        for move in moves:
            new_board = self._apply(board, move)
            score = -self._minimax(new_board, effective_depth, -beta, -alpha,
                                   self._opponent(current_turn), start_time)

            if score > best_score:
                best_score = score
                best_move = move

            alpha = max(alpha, score)
            if alpha >= beta:
                self._store_killer(move, effective_depth)
                logger.debug("beta cutoff", extra={
                    'depth': effective_depth,
                    'move': move,
                    'score': score,
                    'alpha': alpha,
                    'beta': beta,
                })
                break

        self.transposition_table.put(board, effective_depth, best_score, best_move)
        return best_score

    def _eval_for_turn(self, board, current_turn: str) -> int:
        """Return ``_evaluate`` oriented to the side-to-move's perspective.

        ``_evaluate`` is always from the AI's fixed perspective; negamax
        requires scores from the side-to-move's perspective, so we negate
        when it is the opponent's turn.
        """
        score = self._evaluate(board)
        return score if current_turn == self.color else -score

    # ========== Move Ordering ==========

    def _order_moves(self, board, moves: List[Tuple], depth: int) -> List[Tuple]:
        """Order moves to improve alpha-beta efficiency.

        Kept cheap: per-move scoring uses only direct board lookups
        (MVV-LVA, killer/history tables, light positional bonus). The
        previous version called _is_square_attacked and _results_in_check
        (which deep-copies the board and runs a full is_in_check scan) for
        *every* candidate move at every node, dominating search time and
        capping depth. Captures and checks are still found by the search
        itself; ordering only needs to surface the most promising moves
        cheaply to get good alpha-beta cutoffs.
        """
        scored_moves = []

        for move in moves:
            score = 0
            fx, fy, tx, ty = move
            target = board[ty][tx]
            piece = board[fy][fx]
            if piece is None:
                continue

            piece_type = ChessGame.get_piece_type(piece)
            if piece_type is None:
                continue

            # Captures are good (MVV): prefer taking high-value targets
            if target:
                target_type = ChessGame.get_piece_type(target)
                if target_type is None:
                    continue

                score += PIECE_VALUES.get(target_type, 0) * 10
                # MVV-LVA: cheap attacker winning a more valuable piece
                if PIECE_VALUES.get(piece_type, 0) < PIECE_VALUES.get(target_type, 0):
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
            logger.debug("store killer move", extra={
                'depth': depth,
                'killer_moves': self.killer_moves[depth],
                'move': move,
            })

    def _update_history(self, move: Tuple, depth: int, score: int):
        """Update history heuristic table."""
        if move not in self.history_table:
            self.history_table[move] = 0
        self.history_table[move] += depth * depth

    # ========== Evaluation ==========

    def _evaluate(self, board) -> int:
        """Evaluate board position from AI's perspective.

        Kept intentionally cheap so the search can reach greater depth:
        material + piece-square tables + light activity + king safety.

        The previous version also called _mobility_bonus, _threat_bonus and
        a per-piece _is_square_defended at every leaf. Each of those
        regenerated the full legal-move set (or scanned the whole board),
        making a single evaluation ~30k is_valid_move calls. That capped the
        search at roughly 800 nodes in 5s -- too shallow to detect even
        short tactical traps, which is why the engine happily walked into
        the 炮2进7 losing line. Captures and threats are now discovered by
        the search itself, not re-scored statically at the horizon.
        """
        score = 0

        for y in range(10):
            for x in range(9):
                piece = board[y][x]
                if piece is None:
                    continue

                color = ChessGame.get_piece_color(piece)
                if color is None:
                    continue

                ptype = ChessGame.get_piece_type(piece)
                if ptype is None:
                    continue

                value = PIECE_VALUES.get(ptype, 0)

                if ptype in PST:
                    pst = PST[ptype]
                    if color == 'red':
                        value += pst[y][x]
                    else:
                        value += pst[9 - y][x]

                value += self._piece_activity_bonus(board, x, y, color, ptype)

                if color == self.color:
                    score += value
                else:
                    score -= value

        score += self._king_safety_bonus(board, self.color) - self._king_safety_bonus(board, self._opponent(self.color))
        return score

    def _piece_activity_bonus(self, board, x, y, color, ptype) -> int:
        """Small positional bonus for activity and centralization."""
        bonus = 0
        if ptype in ('車', '马', '炮'):
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
        if ptype in ('車', '马', '炮'):
            bonus += max(0, 4 - abs(tx - 4)) * 2
        if ptype in ('兵', '卒'):
            bonus += 2 if tx == 4 else 0
        if ptype in ('帅', '将'):
            bonus += 6 if (3 <= tx <= 5 and 0 <= ty <= 2) or (3 <= tx <= 5 and 7 <= ty <= 9) else 0
        return bonus

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

    def _is_square_attacked(self, board, x, y, color) -> bool:
        """True if any piece of `color` could capture on (x, y).

        The target square is temporarily treated as enemy-occupied for the
        check, so a square defended only by friendly pieces (where the
        defender would be 'capturing' its own piece) is still reported as
        attacked. Without this, is_valid_move rejects moves onto friendly
        squares and defended pieces look hanging -- which made
        _select_tactical_move short-circuit on grabs like 炮2进7 (taking
        the horse at (1,9) that the red rook actually defends) and bypass
        the search entirely. The board cell is restored in a finally block.
        """
        opponent = self._opponent(color)
        enemy_king = 'red_帅' if opponent == 'red' else 'black_将'
        saved = board[y][x]
        board[y][x] = enemy_king  # enemy placeholder so capture rules apply
        try:
            for oy in range(10):
                for ox in range(9):
                    piece = board[oy][ox]
                    if piece is None:
                        continue
                    if ChessGame.get_piece_color(piece) != color:
                        continue
                    if self._sim.is_valid_move(ox, oy, x, y, board=board,
                                               color_override=color, check_king_safety=False):
                        return True
            return False
        finally:
            board[y][x] = saved

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
                    if ptype in ('马', '炮', '車'):
                        if (piece.startswith('red_') and y >= 7) or \
                           (piece.startswith('black_') and y <= 2):
                            count += 1
        return count