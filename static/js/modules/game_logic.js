const INITIAL_BOARD = [
    ['black_车', 'black_马', 'black_象', 'black_士', 'black_将', 'black_士', 'black_象', 'black_马', 'black_车'],
    [null, null, null, null, null, null, null, null, null],
    [null, 'black_炮', null, null, null, null, null, 'black_炮', null],
    ['black_卒', null, 'black_卒', null, 'black_卒', null, 'black_卒', null, 'black_卒'],
    [null, null, null, null, null, null, null, null, null],
    [null, null, null, null, null, null, null, null, null],
    ['red_兵', null, 'red_兵', null, 'red_兵', null, 'red_兵', null, 'red_兵'],
    [null, 'red_炮', null, null, null, null, null, 'red_炮', null],
    [null, null, null, null, null, null, null, null, null],
    ['red_车', 'red_马', 'red_相', 'red_仕', 'red_帅', 'red_仕', 'red_相', 'red_马', 'red_车'],
];

class ChessGame {
    constructor() {
        this.board = JSON.parse(JSON.stringify(INITIAL_BOARD));
        this.current_turn = 'red';
        this.game_over = false;
        this.winner = null;
        this.move_history = [];
    }

    reset() {
        this.board = JSON.parse(JSON.stringify(INITIAL_BOARD));
        this.current_turn = 'red';
        this.game_over = false;
        this.winner = null;
        this.move_history = [];
    }

    make_move(from_x, from_y, to_x, to_y) {
        const piece = this.board[from_y][from_x];
        if (!piece) return false;

        const color = piece.startsWith('red_') ? 'red' : 'black';
        const target = this.board[to_y][to_x];
        if (target && target.startsWith(color === 'red' ? 'red_' : 'black_')) {
            return false;
        }

        this.board[to_y][to_x] = piece;
        this.board[from_y][from_x] = null;

        this.move_history.push({
            from_x, from_y, to_x, to_y,
            piece: piece.split('_')[1],
            color: color,
            description: this._describe_move(piece, from_x, from_y, to_x, to_y, target)
        });

        this.current_turn = color === 'red' ? 'black' : 'red';
        return true;
    }

    _describe_move(piece, from_x, from_y, to_x, to_y, captured) {
        const col_names = '九八七六五四三二一';
        const row_names_red = '一二三四五六七八九';
        
        const color = piece.startsWith('red_') ? 'red' : 'black';
        const piece_name = piece.split('_')[1];
        
        const col_from = col_names[from_x];
        const col_to = col_names[to_x];
        const row_from = row_names_red[8 - from_y];
        const row_to = row_names_red[8 - to_y];
        
        return `${piece_name}${col_from}${row_from}→${col_to}${row_to}`;
    }
}

export { ChessGame, INITIAL_BOARD };