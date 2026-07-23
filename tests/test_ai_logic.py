"""
Unit tests for the lightweight AI engine.

Covers:
- choose_move returns a legal move on the initial board
- the AI captures a hanging (free) piece when available
- the AI never mutates the caller's board
- difficulty changes take effect
- evaluation sign favours the AI when it has a material advantage
- the AI escapes check when it is under attack
"""
import unittest
from copy import deepcopy

from game.core import ChessGame
from game.ai import ChessAI, DIFFICULTY_CONFIG
from game.constants import INITIAL_BOARD


class ChessAITests(unittest.TestCase):

    def setUp(self):
        self.game = ChessGame()

    def _is_legal(self, board, color, move):
        sim = ChessGame()
        sim.board = deepcopy(board)
        sim.current_turn = color
        fx, fy, tx, ty = move
        return sim.is_valid_move(fx, fy, tx, ty, color_override=color)

    # ---------- basic behaviour ----------

    def test_choose_move_returns_legal_move_on_initial_board(self):
        ai = ChessAI(color='black', difficulty='normal')
        move = ai.choose_move(INITIAL_BOARD, 'black')
        self.assertIsNotNone(move)
        self.assertTrue(self._is_legal(INITIAL_BOARD, 'black', move))

    def test_choose_move_returns_none_when_no_moves(self):
        ai = ChessAI(color='black', difficulty='normal')
        board = [[None] * 9 for _ in range(10)]
        board[1][4] = 'black_将'
        board[0][3] = 'red_車'
        board[0][4] = 'red_車'
        board[0][5] = 'red_車'
        board[2][4] = 'red_車'
        board[1][3] = 'red_車'
        board[1][5] = 'red_車'
        move = ai.choose_move(board, 'black')
        self.assertIsNone(move)

    def test_board_is_not_mutated_by_search(self):
        ai = ChessAI(color='black', difficulty='hard')
        snapshot = deepcopy(INITIAL_BOARD)
        ai.choose_move(INITIAL_BOARD, 'black')
        self.assertEqual(INITIAL_BOARD, snapshot)

    # ---------- tactical behaviour ----------

    def test_ai_captures_hanging_piece(self):
        ai = ChessAI(color='black', difficulty='normal')
        board = [[None] * 9 for _ in range(10)]
        board[0][4] = 'black_将'
        board[9][4] = 'red_帅'
        board[5][4] = 'black_車'
        board[6][4] = 'red_炮'
        move = ai.choose_move(board, 'black')
        self.assertIsNotNone(move)
        fx, fy, tx, ty = move
        self.assertEqual((fx, fy), (4, 5))
        self.assertEqual((tx, ty), (4, 6))

    def test_ai_escapes_check(self):
        ai = ChessAI(color='black', difficulty='normal')
        board = [[None] * 9 for _ in range(10)]
        board[0][4] = 'black_将'
        board[9][4] = 'red_帅'
        board[5][4] = 'red_車'
        move = ai.choose_move(board, 'black')
        self.assertIsNotNone(move)
        sim = ChessGame()
        sim.board = deepcopy(board)
        sim.current_turn = 'black'
        fx, fy, tx, ty = move
        self.assertTrue(sim.make_move(fx, fy, tx, ty)['success'])
        self.assertFalse(sim.is_in_check('black'))

    # ---------- configuration ----------

    def test_difficulty_changes_search_depth(self):
        ai = ChessAI(color='black', difficulty='easy')
        self.assertEqual(ai.max_depth, DIFFICULTY_CONFIG['easy']['depth'])
        ai.set_difficulty('hard')
        self.assertEqual(ai.max_depth, DIFFICULTY_CONFIG['hard']['depth'])
        self.assertEqual(ai.difficulty, 'hard')

    def test_invalid_difficulty_raises(self):
        ai = ChessAI(color='black', difficulty='normal')
        with self.assertRaises(ValueError):
            ai.set_difficulty('impossible')

    def test_invalid_color_raises(self):
        with self.assertRaises(ValueError):
            ChessAI(color='blue', difficulty='normal')

    # ---------- evaluation ----------

    def test_evaluation_positive_when_ai_has_material_advantage(self):
        ai = ChessAI(color='black', difficulty='normal')
        board = [[None] * 9 for _ in range(10)]
        board[0][4] = 'black_将'
        board[9][4] = 'red_帅'
        board[0][0] = 'black_車'
        score = ai._evaluate(board)
        self.assertGreater(score, 0)

    def test_evaluation_balanced_on_initial_board(self):
        # With PST, the initial board is not perfectly balanced
        # The score should be small (< 500 points)
        ai = ChessAI(color='black', difficulty='normal')
        score = ai._evaluate(INITIAL_BOARD)
        self.assertLess(abs(score), 500)  # Allow some positional imbalance


if __name__ == '__main__':
    unittest.main()
