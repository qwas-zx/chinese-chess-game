"""
Chinese Chess Game - Import/Export Format Converters

Supports four interchange formats:

* **FEN**  - Xiangqi position string (board + turn only, no history).
             Example: ``rnbakabnr/9/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/1C5C1/9/RNBAKABNR w - - 0 1``
* **TXT**  - Human-readable Chinese notation, one round per line.
* **PGN**  - Portable Game Notation with coordinate-style moves
             (e.g. ``b0c2``). Headers + movetext, easy to extend.
* **Save** - Existing JSON-embedded backup format (handled elsewhere).

Piece letter convention (de-facto Xiangqi standard used by most engines):

    K/k = King (帅/将)      A/a = Advisor (仕/士)     B/b = Elephant (相/象)
    N/n = Horse (马)        R/r = Rook (車)           C/c = Cannon (炮)
    P/p = Pawn (兵/卒)

Uppercase = red, lowercase = black. Board layout in FEN is the same as the
internal representation: top row first (black side), 9 columns wide.
"""
import re
from copy import deepcopy
from typing import List, Optional, Tuple

from .constants import BOARD_HEIGHT, BOARD_WIDTH, INITIAL_BOARD

# ---------- Piece <-> letter ----------

PIECE_TO_FEN = {
    'red_帅': 'K', 'red_仕': 'A', 'red_相': 'B', 'red_马': 'N',
    'red_車': 'R', 'red_炮': 'C', 'red_兵': 'P',
    'black_将': 'k', 'black_士': 'a', 'black_象': 'b', 'black_马': 'n',
    'black_車': 'r', 'black_炮': 'c', 'black_卒': 'p',
}
FEN_TO_PIECE = {letter: piece for piece, letter in PIECE_TO_FEN.items()}


# ---------- FEN ----------

def board_to_fen(board: List[List[Optional[str]]], current_turn: str = 'red') -> str:
    """Encode a board + turn into a FEN string.

    The ``- - 0 1`` tail mirrors the international-chess FEN layout so the
    string is accepted by strict parsers, but only the position and turn
    fields are meaningful for Xiangqi.
    """
    rows = []
    for y in range(BOARD_HEIGHT):
        row = ''
        empty = 0
        for x in range(BOARD_WIDTH):
            piece = board[y][x]
            if piece:
                if empty:
                    row += str(empty)
                    empty = 0
                row += PIECE_TO_FEN.get(piece, '?')
            else:
                empty += 1
        if empty:
            row += str(empty)
        rows.append(row)
    turn = 'b' if current_turn == 'black' else 'w'
    return f"{'/'.join(rows)} {turn} - - 0 1"


def fen_to_board(fen: str) -> Tuple[List[List[Optional[str]]], str]:
    """Parse a FEN string into (board, current_turn).

    Accepts both a full FEN (``position turn - - 0 1``) and a bare position
    field. Raises ``ValueError`` on malformed input.
    """
    if not fen or not fen.strip():
        raise ValueError('FEN 为空')
    parts = fen.strip().split()
    field = parts[0]
    rows = field.split('/')
    if len(rows) != BOARD_HEIGHT:
        raise ValueError(f'FEN 需要 {BOARD_HEIGHT} 行棋盘，得到 {len(rows)} 行')
    board: List[List[Optional[str]]] = [[None] * BOARD_WIDTH for _ in range(BOARD_HEIGHT)]
    for y, row in enumerate(rows):
        x = 0
        for ch in row:
            if ch.isdigit():
                x += int(ch)
            else:
                if ch not in FEN_TO_PIECE:
                    raise ValueError(f'未知 FEN 字符: {ch!r}')
                if x >= BOARD_WIDTH:
                    raise ValueError(f'FEN 第 {y + 1} 行宽度超过 {BOARD_WIDTH}')
                board[y][x] = FEN_TO_PIECE[ch]
                x += 1
        if x != BOARD_WIDTH:
            raise ValueError(f'FEN 第 {y + 1} 行宽度不足 {BOARD_WIDTH}')
    turn = 'black' if (len(parts) > 1 and parts[1].lower() == 'b') else 'red'
    return board, turn


# ---------- Plain-text notation ----------

def history_to_plain_text(move_history, game_over=False, winner=None) -> str:
    """Render move history as plain Chinese notation, one round per line.

    Example::

        1. 炮二平五\t马8进7
        2. 马二进三\t车9平8
    """
    lines: List[str] = []
    if game_over:
        if winner == 'draw':
            lines.append('结果：和棋')
        elif winner:
            lines.append(f"结果：{'红方' if winner == 'red' else '黑方'}胜")
    if not move_history:
        lines.append('（暂无走棋记录）')
        return '\n'.join(lines)
    for i in range(0, len(move_history), 2):
        round_num = i // 2 + 1
        red = _move_desc(move_history[i])
        black = _move_desc(move_history[i + 1]) if i + 1 < len(move_history) else ''
        lines.append(f'{round_num}. {red}\t{black}'.rstrip())
    return '\n'.join(lines)


def _move_desc(record) -> str:
    """Pull a human-readable description out of a move-history record.

    The server stores ``description``; the frontend deduce module uses
    ``piece`` + coordinates. We tolerate either shape.
    """
    if not record:
        return ''
    if isinstance(record, dict):
        if record.get('description'):
            return str(record['description'])
        if record.get('piece'):
            piece = str(record['piece'])
            name = piece.split('_')[-1] if '_' in piece else piece
            return name
    return str(record)


# ---------- PGN ----------

def _coord_to_square(x: int, y: int) -> str:
    """``(x, y)`` -> PGN square id. Columns a-i (a = x=0), rows 0-9
    (0 = red's back rank = y=9)."""
    return chr(97 + x) + str(9 - y)


def _square_to_coord(sq: str) -> Tuple[int, int]:
    if len(sq) < 2:
        raise ValueError(f'非法坐标: {sq!r}')
    x = ord(sq[0]) - 97
    y = 9 - int(sq[1:])
    if not (0 <= x < BOARD_WIDTH and 0 <= y < BOARD_HEIGHT):
        raise ValueError(f'坐标超出棋盘: {sq!r}')
    return x, y


def history_to_pgn(move_history, game_over=False, winner=None, event: str = '中国象棋') -> str:
    """Generate a PGN string with coordinate-style moves.

    Moves are written as ``<from><to>`` (e.g. ``b0c2``). The movetext is
    numbered in standard PGN style (``1. b0c2 c9c7 2. ...``).
    """
    if game_over:
        if winner == 'draw':
            result = '1/2-1/2'
        elif winner == 'red':
            result = '1-0'
        elif winner == 'black':
            result = '0-1'
        else:
            result = '*'
    else:
        result = '*'

    from datetime import date
    today = date.today().strftime('%Y.%m.%d')

    headers = [
        f'[Event "{event}"]',
        '[Site "Local"]',
        f'[Date "{today}"]',
        '[Variant "Xiangqi"]',
        f'[Result "{result}"]',
    ]

    tokens: List[str] = []
    for i, mv in enumerate(move_history):
        if not isinstance(mv, dict):
            continue
        fx, fy, tx, ty = _extract_coords(mv)
        if fx is None:
            continue
        if i % 2 == 0:
            tokens.append(f'{i // 2 + 1}.')
        tokens.append(_coord_to_square(fx, fy) + _coord_to_square(tx, ty))
    tokens.append(result)
    body = ' '.join(tokens)
    return '\n'.join(headers) + '\n\n' + body


def pgn_to_moves(pgn: str) -> List[Tuple[int, int, int, int]]:
    """Extract ``[(from_x, from_y, to_x, to_y), ...]`` from a PGN string.

    Only coordinate-style moves (4 chars: ``a-i`` + digit + ``a-i`` + digit)
    are recognised. Headers ``[...]`` and comments ``{...}`` are stripped.
    Move numbers, ``*``, ``1-0`` etc. are ignored.
    """
    if not pgn:
        return []
    cleaned = re.sub(r'\[[^\]]*\]', ' ', pgn)
    cleaned = re.sub(r'\{[^}]*\}', ' ', cleaned)
    cleaned = re.sub(r';[^\n]*', ' ', cleaned)

    moves: List[Tuple[int, int, int, int]] = []
    for m in re.finditer(r'([a-i])(\d)([a-i])(\d)', cleaned):
        try:
            fx, fy = _square_to_coord(m.group(1) + m.group(2))
            tx, ty = _square_to_coord(m.group(3) + m.group(4))
        except ValueError:
            continue
        moves.append((fx, fy, tx, ty))
    return moves


def _extract_coords(record) -> Tuple[Optional[int], Optional[int], Optional[int], Optional[int]]:
    """Pull (from_x, from_y, to_x, to_y) out of a move-history record,
    tolerating both the server (nested ``from``/``to``) and frontend
    (flat ``from_x``/``to_y``) shapes."""
    if not isinstance(record, dict):
        return None, None, None, None
    fx = record.get('from_x')
    fy = record.get('from_y')
    tx = record.get('to_x')
    ty = record.get('to_y')
    if fx is None and isinstance(record.get('from'), dict):
        fx = record['from'].get('x')
        fy = record['from'].get('y')
        tx = record['to'].get('x')
        ty = record['to'].get('y')
    return fx, fy, tx, ty


# ---------- Convenience: starting position ----------

def initial_fen() -> str:
    """FEN of the standard starting position."""
    return board_to_fen(INITIAL_BOARD, 'red')


def parse_import_payload(payload: dict):
    """Normalise an /api/import payload into (board, current_turn, move_history).

    Accepts any of:
      - ``{board, current_turn, move_history}`` (existing save format)
      - ``{fen: "..."}``                          (FEN position only)
      - ``{pgn: "..."}``                          (PGN movetext, replayed)
      - ``{fen, pgn}``                            (FEN as starting position, PGN as moves)

    For PGN, moves are replayed on top of the parsed FEN (or the initial
    board if no FEN is given) so the resulting ``move_history`` matches what
    the server would produce for the same sequence.

    Returns ``(board, current_turn, move_history)`` or raises ``ValueError``.
    """
    if not isinstance(payload, dict):
        raise ValueError('导入数据无效')

    board = None
    current_turn = 'red'
    move_history = []

    fen = payload.get('fen')
    if fen:
        board, current_turn = fen_to_board(fen)

    if 'board' in payload and payload['board']:
        if board is not None:
            raise ValueError('不能同时指定 fen 和 board')
        b = payload['board']
        if not (isinstance(b, list) and len(b) == BOARD_HEIGHT):
            raise ValueError('棋盘格式无效')
        board = deepcopy(b)
        current_turn = payload.get('current_turn') or 'red'
        move_history = deepcopy(payload.get('move_history') or [])

    if board is None:
        board = deepcopy(INITIAL_BOARD)

    pgn = payload.get('pgn')
    if pgn:
        # Replay moves on top of the (possibly FEN-supplied) board.
        from .core import ChessGame
        sim = ChessGame()
        sim.board = deepcopy(board)
        sim.current_turn = current_turn
        sim.move_history = []
        for fx, fy, tx, ty in pgn_to_moves(pgn):
            piece = sim.board[fy][fx]
            if piece is None:
                raise ValueError(f'PGN 走法非法: 第 {len(sim.move_history) + 1} 步起点无棋子')
            sim.current_turn = 'red' if piece.startswith('red_') else 'black'
            result = sim.make_move(fx, fy, tx, ty)
            if not result.get('success'):
                raise ValueError(f'PGN 走法非法: 第 {len(sim.move_history)} 步 {result.get("message")}')
        board = sim.board
        current_turn = sim.current_turn
        move_history = sim.move_history

    return board, current_turn, move_history
