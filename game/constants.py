"""
Chinese Chess Game - Constants
"""
from copy import deepcopy

# Initial board setup (black at top, red at bottom)
INITIAL_BOARD = [
    ['black_車', 'black_马', 'black_象', 'black_士', 'black_将', 'black_士', 'black_象', 'black_马', 'black_車'],
    [None, None, None, None, None, None, None, None, None],
    [None, 'black_炮', None, None, None, None, None, 'black_炮', None],
    ['black_卒', None, 'black_卒', None, 'black_卒', None, 'black_卒', None, 'black_卒'],
    [None, None, None, None, None, None, None, None, None],
    [None, None, None, None, None, None, None, None, None],
    ['red_兵', None, 'red_兵', None, 'red_兵', None, 'red_兵', None, 'red_兵'],
    [None, 'red_炮', None, None, None, None, None, 'red_炮', None],
    [None, None, None, None, None, None, None, None, None],
    ['red_車', 'red_马', 'red_相', 'red_仕', 'red_帅', 'red_仕', 'red_相', 'red_马', 'red_車'],
]

# Piece display names
PIECE_NAMES = {
    'red_帅': '帅', 'red_仕': '仕', 'red_相': '相', 'red_马': '马',
    'red_車': '車', 'red_炮': '炮', 'red_兵': '兵',
    'black_将': '将', 'black_士': '士', 'black_象': '象', 'black_马': '马',
    'black_車': '車', 'black_炮': '炮', 'black_卒': '卒',
}

# Column names for Chinese notation (red's perspective)
COL_NAMES = ['九', '八', '七', '六', '五', '四', '三', '二', '一']

# Board dimensions
BOARD_WIDTH = 9
BOARD_HEIGHT = 10