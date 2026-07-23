import unittest

from game.core import ChessGame


class ChessGameRuleTests(unittest.TestCase):
    def test_pawn_cannot_move_sideways_after_crossing_river(self):
        game = ChessGame()
        game.current_turn = 'red'
        game.board = [[None] * 9 for _ in range(10)]
        game.board[5][4] = 'red_兵'

        self.assertTrue(game.is_valid_move(4, 5, 4, 4))
        self.assertFalse(game.is_valid_move(4, 5, 3, 5))
        self.assertFalse(game.is_valid_move(4, 5, 5, 5))

    def test_checkmate_is_detected_when_no_escape_moves(self):
        game = ChessGame()
        game.current_turn = 'red'
        game.board = [[None] * 9 for _ in range(10)]
        game.board[9][3] = 'red_帅'
        game.board[0][3] = 'black_車'
        game.board[0][2] = 'black_車'
        game.board[0][4] = 'black_車'

        self.assertTrue(game.is_in_check('red'))
        self.assertTrue(game.is_checkmate('red'))


if __name__ == '__main__':
    unittest.main()
