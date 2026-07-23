"""
Chinese Chess Game - Core Game Logic
"""
from copy import deepcopy
from .constants import INITIAL_BOARD, PIECE_NAMES, COL_NAMES, BOARD_WIDTH, BOARD_HEIGHT


class ChessGame:
    """Main game state and logic class"""

    def __init__(self):
        self.board = deepcopy(INITIAL_BOARD)
        self.current_turn = 'red'
        self.game_over = False
        self.winner = None
        self.flipped = False
        self.move_history = []
        self.draw_requested_by = None
        self.adjust_mode = False

    def reset(self):
        """Reset game to initial state"""
        self.board = deepcopy(INITIAL_BOARD)
        self.current_turn = 'red'
        self.game_over = False
        self.winner = None
        self.flipped = False
        self.move_history = []
        self.draw_requested_by = None
        self.adjust_mode = False

    # ========== Piece Helpers ==========

    @staticmethod
    def get_piece_color(piece):
        """Get color of a piece ('red' or 'black')"""
        if piece is None:
            return None
        return 'red' if piece.startswith('red_') else 'black'

    @staticmethod
    def get_piece_type(piece):
        """Get type of a piece (帅, 将, 車, etc.)"""
        if piece is None:
            return None
        return piece.split('_')[1]

    @staticmethod
    def is_valid_position(x, y):
        """Check if position is within board bounds"""
        return 0 <= x < BOARD_WIDTH and 0 <= y < BOARD_HEIGHT

    def is_in_palace(self, x, y, color):
        """Check if position is within the palace for given color"""
        if not (3 <= x <= 5):
            return False
        if color == 'red':
            return 7 <= y <= 9
        return 0 <= y <= 2

    def has_piece(self, x, y, board=None):
        """Check if there's a piece at position"""
        board = self.board if board is None else board
        return board[y][x] is not None

    def count_pieces_between(self, x1, y1, x2, y2, board=None):
        """Count pieces between two positions on same line"""
        board = self.board if board is None else board
        count = 0
        if x1 == x2:
            start, end = sorted([y1, y2])
            for y in range(start + 1, end):
                if self.has_piece(x1, y, board):
                    count += 1
        elif y1 == y2:
            start, end = sorted([x1, x2])
            for x in range(start + 1, end):
                if self.has_piece(x, y1, board):
                    count += 1
        return count

    # ========== Move Description ==========

    def describe_move(self, piece, from_x, from_y, to_x, to_y, captured):
        """Generate Chinese notation for a move"""
        color = self.get_piece_color(piece)
        color_name = '红' if color == 'red' else '黑'
        piece_name = PIECE_NAMES.get(piece, self.get_piece_type(piece))

        if color == 'red':
            from_col = COL_NAMES[from_x]
            to_col = COL_NAMES[to_x]
        else:
            from_col = str(from_x + 1)
            to_col = str(to_x + 1)

        dy = to_y - from_y
        if color == 'red':
            forward = '进' if dy < 0 else '退' if dy > 0 else '平'
        else:
            forward = '进' if dy > 0 else '退' if dy < 0 else '平'

        if from_x == to_x:
            dest = str(abs(dy))
        else:
            dest = to_col

        return f"{color_name}{piece_name}{from_col}{forward}{dest}"

    # ========== Move Validation ==========

    def is_valid_move(self, from_x, from_y, to_x, to_y, board=None, color_override=None, check_king_safety=True):
        """Validate a move from (from_x, from_y) to (to_x, to_y).

        When ``check_king_safety`` is False the "would leave own king in
        check" test is skipped — used by the AI search to speed up move
        generation (king safety is enforced at the root instead).
        """
        board = self.board if board is None else board
        color_override = self.current_turn if color_override is None else color_override

        if not self.is_valid_position(from_x, from_y):
            return False
        if not self.is_valid_position(to_x, to_y):
            return False

        piece = board[from_y][from_x]
        if piece is None:
            return False

        color = self.get_piece_color(piece)
        if color != color_override:
            return False

        target_piece = board[to_y][to_x]
        if target_piece and self.get_piece_color(target_piece) == color:
            return False

        if from_x == to_x and from_y == to_y:
            return False

        piece_type = self.get_piece_type(piece)
        validators = {
            ('帅', '将'): self._validate_king,
            ('仕', '士'): self._validate_advisor,
            ('相', '象'): self._validate_elephant,
            ('马',): self._validate_horse,
            ('車',): self._validate_rook,
            ('炮',): self._validate_cannon,
            ('兵', '卒'): self._validate_pawn,
        }

        for types, validator in validators.items():
            if piece_type in types:
                if not validator(from_x, from_y, to_x, to_y, color, board):
                    return False
                if not check_king_safety:
                    return True
                return not self._would_leave_king_in_check(board, from_x, from_y, to_x, to_y, color)

        return False

    def _validate_king(self, from_x, from_y, to_x, to_y, color, board=None):
        board = self.board if board is None else board
        if not self.is_in_palace(to_x, to_y, color):
            return False
        dx, dy = abs(to_x - from_x), abs(to_y - from_y)
        if (dx == 1 and dy == 0) or (dx == 0 and dy == 1):
            return True
        if dx == 0:
            target = board[to_y][to_x]
            if target and self.get_piece_type(target) in ('帅', '将'):
                return self.count_pieces_between(from_x, from_y, to_x, to_y, board) == 0
        return False

    def _validate_advisor(self, from_x, from_y, to_x, to_y, color, board=None):
        if not self.is_in_palace(to_x, to_y, color):
            return False
        return abs(to_x - from_x) == 1 and abs(to_y - from_y) == 1

    def _validate_elephant(self, from_x, from_y, to_x, to_y, color, board=None):
        if abs(to_x - from_x) != 2 or abs(to_y - from_y) != 2:
            return False
        mid_x, mid_y = (from_x + to_x) // 2, (from_y + to_y) // 2
        if self.has_piece(mid_x, mid_y, board):
            return False
        if color == 'red' and to_y < 5:
            return False
        if color == 'black' and to_y > 4:
            return False
        return True

    def _validate_horse(self, from_x, from_y, to_x, to_y, color=None, board=None):
        board = self.board if board is None else board
        dx, dy = abs(to_x - from_x), abs(to_y - from_y)
        if not ((dx == 1 and dy == 2) or (dx == 2 and dy == 1)):
            return False
        leg_x = (from_x + to_x) // 2 if dx == 2 else from_x
        leg_y = (from_y + to_y) // 2 if dy == 2 else from_y
        return not self.has_piece(leg_x, leg_y, board)

    def _validate_rook(self, from_x, from_y, to_x, to_y, color=None, board=None):
        board = self.board if board is None else board
        if from_x != to_x and from_y != to_y:
            return False
        return self.count_pieces_between(from_x, from_y, to_x, to_y, board) == 0

    def _validate_cannon(self, from_x, from_y, to_x, to_y, color=None, board=None):
        board = self.board if board is None else board
        if from_x != to_x and from_y != to_y:
            return False
        pieces_between = self.count_pieces_between(from_x, from_y, to_x, to_y, board)
        target_piece = board[to_y][to_x]
        if target_piece is None:
            return pieces_between == 0
        return pieces_between == 1

    def _validate_pawn(self, from_x, from_y, to_x, to_y, color, board=None):
        dx, dy = to_x - from_x, to_y - from_y
        if color == 'red':
            if dy > 0:
                return False
            if from_y >= 5:
                return dx == 0 and dy == -1
            return dx == 0 and dy == -1
        else:
            if dy < 0:
                return False
            if from_y <= 4:
                return dx == 0 and dy == 1
            return dx == 0 and dy == 1

    def _simulate_move(self, board, from_x, from_y, to_x, to_y):
        board_copy = deepcopy(board)
        piece = board_copy[from_y][from_x]
        board_copy[to_y][to_x] = piece
        board_copy[from_y][from_x] = None
        return board_copy

    def _would_leave_king_in_check(self, board, from_x, from_y, to_x, to_y, color):
        board_after = self._simulate_move(board, from_x, from_y, to_x, to_y)
        return self.is_in_check(color, board_after)

    def _find_king_position(self, board, color):
        king_piece = 'red_帅' if color == 'red' else 'black_将'
        for y, row in enumerate(board):
            for x, piece in enumerate(row):
                if piece == king_piece:
                    return x, y
        return None

    def is_in_check(self, color, board=None):
        board = self.board if board is None else board
        king_position = self._find_king_position(board, color)
        if king_position is None:
            return False

        king_x, king_y = king_position
        for y in range(10):
            for x in range(9):
                piece = board[y][x]
                if piece is None:
                    continue
                if self.get_piece_color(piece) == color:
                    continue
                original_board = self.board
                original_turn = self.current_turn
                self.board = board
                self.current_turn = self.get_piece_color(piece)
                try:
                    if self.is_valid_move(x, y, king_x, king_y, board=board, color_override=self.get_piece_color(piece)):
                        return True
                finally:
                    self.board = original_board
                    self.current_turn = original_turn
        return False

    def get_legal_moves(self, color=None, board=None):
        board = self.board if board is None else board
        color = self.current_turn if color is None else color
        moves = []
        for y in range(10):
            for x in range(9):
                piece = board[y][x]
                if piece is None:
                    continue
                if self.get_piece_color(piece) != color:
                    continue
                for tx in range(9):
                    for ty in range(10):
                        if self.is_valid_move(x, y, tx, ty, board=board, color_override=color):
                            moves.append({'x': tx, 'y': ty})
        return moves

    def is_checkmate(self, color=None, board=None):
        board = self.board if board is None else board
        color = self.current_turn if color is None else color
        return self.is_in_check(color, board) and not self.get_legal_moves(color, board)

    # ========== Game Actions ==========

    def make_move(self, from_x, from_y, to_x, to_y):
        """Execute a move"""
        if self.game_over:
            return {'success': False, 'message': '游戏已结束'}

        if not self.is_valid_move(from_x, from_y, to_x, to_y):
            return {'success': False, 'message': '无效的移动'}

        piece = self.board[from_y][from_x]
        moving_color = self.get_piece_color(piece)
        captured = self.board[to_y][to_x]
        self.board[to_y][to_x] = piece
        self.board[from_y][from_x] = None

        move_desc = self.describe_move(piece, from_x, from_y, to_x, to_y, captured)
        self.move_history.append({
            'from': {'x': from_x, 'y': from_y},
            'to': {'x': to_x, 'y': to_y},
            'piece': piece,
            'captured': captured,
            'description': move_desc
        })

        if captured:
            captured_type = self.get_piece_type(captured)
            if captured_type in ('帅', '将'):
                self.game_over = True
                self.winner = moving_color

        self.current_turn = 'black' if moving_color == 'red' else 'red'
        self.draw_requested_by = None

        status_message = ''
        if not self.game_over:
            opponent_color = self.current_turn
            if self.is_in_check(opponent_color):
                if self.is_checkmate(opponent_color):
                    self.game_over = True
                    self.winner = moving_color
                    status_message = '绝杀！'
                else:
                    status_message = '将军！'

        return {
            'success': True,
            'board': self.board,
            'current_turn': self.current_turn,
            'captured': captured,
            'game_over': self.game_over,
            'winner': self.winner,
            'move_description': move_desc,
            'move_history': self.move_history,
            'message': status_message or None,
            'check': bool(status_message),
            'checkmate': status_message == '绝杀！'
        }

    def undo(self):
        """Undo last move"""
        if not self.move_history:
            return {'success': False, 'message': '没有可撤销的走法'}

        last_move = self.move_history.pop()
        fx, fy = last_move['from']['x'], last_move['from']['y']
        tx, ty = last_move['to']['x'], last_move['to']['y']

        self.board[fy][fx] = last_move['piece']
        self.board[ty][tx] = last_move['captured']

        self.current_turn = 'black' if self.current_turn == 'red' else 'red'
        self.game_over = False
        self.winner = None
        self.draw_requested_by = None

        return {
            'success': True,
            'board': self.board,
            'current_turn': self.current_turn,
            'game_over': self.game_over,
            'winner': self.winner,
            'move_history': self.move_history
        }

    def flip(self):
        """Toggle board flip state"""
        self.flipped = not self.flipped
        return {'success': True, 'flipped': self.flipped}

    def resign(self):
        """Current player resigns"""
        if self.game_over:
            return {'success': False, 'message': '游戏已结束'}
        self.game_over = True
        self.winner = 'black' if self.current_turn == 'red' else 'red'
        return {
            'success': True,
            'game_over': True,
            'winner': self.winner,
            'board': self.board,
            'current_turn': self.current_turn
        }

    def request_draw(self):
        """Request a draw"""
        if self.game_over:
            return {'success': False, 'message': '游戏已结束'}
        if self.draw_requested_by is None:
            self.draw_requested_by = self.current_turn
            return {
                'success': True,
                'draw_requested': True,
                'requested_by': self.draw_requested_by,
                'message': f"{'红方' if self.draw_requested_by == 'red' else '黑方'}请求求和，等待对方回应"
            }
        if self.draw_requested_by == self.current_turn:
            return {'success': False, 'message': '你已经请求过求和了'}
        self.game_over = True
        self.winner = 'draw'
        return {
            'success': True,
            'draw_accepted': True,
            'game_over': True,
            'winner': 'draw',
            'board': self.board
        }

    def accept_draw(self):
        """Accept a draw request"""
        if self.game_over:
            return {'success': False, 'message': '游戏已结束'}
        if self.draw_requested_by is None:
            return {'success': False, 'message': '没有求和请求'}
        self.game_over = True
        self.winner = 'draw'
        return {
            'success': True,
            'draw_accepted': True,
            'game_over': True,
            'winner': 'draw',
            'board': self.board,
            'current_turn': self.current_turn
        }

    def decline_draw(self):
        """Decline a draw request"""
        if self.draw_requested_by is None:
            return {'success': False, 'message': '没有求和请求'}
        self.draw_requested_by = None
        return {'success': True, 'draw_requested': False, 'message': '求和已拒绝'}

    def adjust_piece(self, action, x, y, piece=None):
        """Add, remove, or replace a piece on the board"""
        if not self.is_valid_position(x, y):
            return {'success': False, 'message': '无效位置'}

        if action == 'add':
            if self.board[y][x] is not None:
                return {'success': False, 'message': '该位置已有棋子'}
            if piece is None:
                return {'success': False, 'message': '未指定棋子'}
            self.board[y][x] = piece
        elif action == 'remove':
            if self.board[y][x] is None:
                return {'success': False, 'message': '该位置没有棋子'}
            self.board[y][x] = None
        elif action == 'replace':
            if piece is None:
                return {'success': False, 'message': '未指定棋子'}
            self.board[y][x] = piece
        else:
            return {'success': False, 'message': '无效操作'}

        return {
            'success': True,
            'board': self.board,
            'current_turn': self.current_turn,
            'game_over': self.game_over,
            'winner': self.winner
        }

    def import_state(self, board, current_turn, move_history):
        """Import game state from saved data"""
        if board and isinstance(board, list) and len(board) == BOARD_HEIGHT:
            self.board = deepcopy(board)
            self.current_turn = current_turn or 'red'
            self.move_history = deepcopy(move_history) if move_history else []
            self.game_over = False
            self.winner = None
            self.draw_requested_by = None
            self.adjust_mode = False
            self.flipped = False
            return True
        return False