"""Smoke tests for the FEN / PGN / TXT converters in game.io_formats.

These exercise round-trip behaviour for the new interchange formats added
to import/export. They don't depend on Flask, the database, or any
network, so they can run as a plain unittest suite.
"""
import unittest

from game.core import ChessGame
from game.io_formats import (
    board_to_fen, fen_to_board,
    history_to_plain_text, history_to_pgn, pgn_to_moves,
    parse_import_payload, initial_fen,
)
from game.constants import INITIAL_BOARD


# Canonical FEN for the standard Xiangqi starting position.
START_FEN = 'rnbakabnr/9/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/1C5C1/9/RNBAKABNR w - - 0 1'


class FenRoundTripTests(unittest.TestCase):
    def test_initial_position_fen(self):
        self.assertEqual(initial_fen(), START_FEN)

    def test_board_to_fen_matches_starting(self):
        fen = board_to_fen(INITIAL_BOARD, 'red')
        # Position field (first token) must match the canonical start.
        self.assertEqual(fen.split()[0], START_FEN.split()[0])
        self.assertTrue(fen.startswith('rnbakabnr/'))
        self.assertIn(' w ', fen)  # red to move

    def test_fen_round_trip_preserves_board_and_turn(self):
        fen = board_to_fen(INITIAL_BOARD, 'black')
        board, turn = fen_to_board(fen)
        self.assertEqual(turn, 'black')
        self.assertEqual(board, INITIAL_BOARD)

    def test_bare_position_field_is_accepted(self):
        # Without the "w - - 0 1" tail, default turn should be red.
        board, turn = fen_to_board(START_FEN.split()[0])
        self.assertEqual(turn, 'red')
        self.assertEqual(board, INITIAL_BOARD)

    def test_invalid_fen_raises(self):
        bad_cases = [
            '',                          # empty
            'rnbakabnr/9',               # too few rows
            'rnbakabnr/9/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/1C5C1/9',  # only 9 rows
            'xxxxxxxxx/9/9/9/9/9/9/9/9/9 w - - 0 1',  # bad letter
        ]
        for bad in bad_cases:
            with self.subTest(fen=bad):
                with self.assertRaises(ValueError):
                    fen_to_board(bad)


class PlainTextTests(unittest.TestCase):
    def test_empty_history_produces_placeholder(self):
        text = history_to_plain_text([], game_over=False, winner=None)
        self.assertEqual(text.strip(), '（暂无走棋记录）')

    def test_winner_is_annotated(self):
        text = history_to_plain_text([], game_over=True, winner='red')
        self.assertIn('红方胜', text)

    def test_history_renders_in_rounds(self):
        g = ChessGame()
        # Red horse b0c2: (1,9) -> (2,7). Black horse b9c7: (1,0) -> (2,2).
        g.make_move(1, 9, 2, 7)
        g.make_move(1, 0, 2, 2)
        text = history_to_plain_text(g.move_history, game_over=False, winner=None)
        self.assertIn('1. ', text)
        # Two moves should appear on the same first line.
        first_line = text.splitlines()[0]
        self.assertEqual(len(first_line.split('\t')), 2)


class PgnRoundTripTests(unittest.TestCase):
    def test_pgn_round_trip_replays_same_position(self):
        g = ChessGame()
        g.make_move(1, 9, 2, 7)  # red horse b0c2
        g.make_move(1, 0, 2, 2)  # black horse b9c7
        pgn = history_to_pgn(g.move_history, game_over=False, winner=None)
        # The movetext must include both moves in coordinate form.
        self.assertIn('1. b0c2 b9c7', pgn)

        moves = pgn_to_moves(pgn)
        self.assertEqual(len(moves), 2)
        self.assertEqual(moves[0], (1, 9, 2, 7))
        self.assertEqual(moves[1], (1, 0, 2, 2))

    def test_pgn_result_headers(self):
        pgn_win = history_to_pgn([], game_over=True, winner='red')
        self.assertIn('[Result "1-0"]', pgn_win)
        self.assertTrue(pgn_win.rstrip().endswith('1-0'))

        pgn_draw = history_to_pgn([], game_over=True, winner='draw')
        self.assertIn('[Result "1/2-1/2"]', pgn_draw)

        pgn_ongoing = history_to_pgn([], game_over=False, winner=None)
        self.assertTrue(pgn_ongoing.rstrip().endswith('*'))

    def test_pgn_to_moves_ignores_headers_and_comments(self):
        pgn = (
            '[Event "test"]\n'
            '[Variant "Xiangqi"]\n\n'
            '{this is a comment}\n'
            '1. b0c2 b9c7 2. h2e2 *'
        )
        moves = pgn_to_moves(pgn)
        self.assertEqual(len(moves), 3)
        self.assertEqual(moves[0], (1, 9, 2, 7))
        self.assertEqual(moves[2], (7, 7, 4, 7))


class ImportPayloadTests(unittest.TestCase):
    def test_fen_only_payload(self):
        board, turn, history = parse_import_payload({'fen': START_FEN})
        self.assertEqual(board, INITIAL_BOARD)
        self.assertEqual(turn, 'red')
        self.assertEqual(history, [])

    def test_board_payload_still_works(self):
        # The legacy /api/import payload shape must still be accepted.
        payload = {
            'board': INITIAL_BOARD,
            'current_turn': 'red',
            'move_history': [],
        }
        board, turn, history = parse_import_payload(payload)
        self.assertEqual(board, INITIAL_BOARD)
        self.assertEqual(turn, 'red')

    def test_fen_and_board_conflict_rejected(self):
        with self.assertRaises(ValueError):
            parse_import_payload({'fen': START_FEN, 'board': INITIAL_BOARD})

    def test_non_dict_payload_raises(self):
        with self.assertRaisesRegex(ValueError, '导入数据无效'):
            parse_import_payload('foo')

    def test_invalid_fen_in_payload_raises(self):
        # Xiangqi boards have 10 ranks; this FEN only has 4, which is invalid.
        bad_fen = '9/9/9/9'
        with self.assertRaises(ValueError):
            parse_import_payload({'fen': bad_fen})

    def test_invalid_board_shape_raises(self):
        # Board shape is wrong (1x1 instead of the expected 10x9).
        bad_board = [[None]]
        payload = {
            'board': bad_board,
            'current_turn': 'red',
            'move_history': [],
        }
        with self.assertRaisesRegex(ValueError, '棋盘格式无效'):
            parse_import_payload(payload)

    def test_pgn_same_side_twice_is_rejected(self):
        # Two consecutive red moves must be rejected by turn alternation.
        # b0c2 is a red horse move; b9c7 starts from a black square so the
        # second move would also need to be red to be replayed back-to-back.
        # Here we force two red-origin moves in a row: b0c2 then h0g2 (both
        # red horses). The second must fail because it's black's turn.
        with self.assertRaises(ValueError):
            parse_import_payload({'pgn': '1. b0c2 h0g2'})

    def test_pgn_replays_from_start(self):
        # PGN alone starts from the standard initial position.
        pgn = '1. b0c2 b9c7'
        board, turn, history = parse_import_payload({'pgn': pgn})
        self.assertEqual(len(history), 2)
        # Red horse moved from (1,9) to (2,7); black horse from (1,0) to (2,2).
        self.assertIsNone(board[9][1])
        self.assertEqual(board[7][2], 'red_马')
        self.assertIsNone(board[0][1])
        self.assertEqual(board[2][2], 'black_马')

    def test_fen_plus_pgn_combines(self):
        # Use a FEN that places a lone red rook at a0, then push it.
        custom_fen = '9/9/9/9/9/9/9/9/9/R8 w - - 0 1'
        pgn = '1. a0a1'
        board, turn, history = parse_import_payload({'fen': custom_fen, 'pgn': pgn})
        self.assertEqual(len(history), 1)
        # Rook moved from (0,9) to (0,8).
        self.assertIsNone(board[9][0])
        self.assertEqual(board[8][0], 'red_車')

    def test_invalid_pgn_move_raises(self):
        # a0a0 = no movement, which the move validator rejects.
        with self.assertRaises(ValueError):
            parse_import_payload({'pgn': '1. a0a0'})


if __name__ == '__main__':
    unittest.main()
