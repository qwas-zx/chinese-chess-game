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

    static getPieceColor(piece) {
        if (!piece) return null;
        return piece.startsWith('red_') ? 'red' : 'black';
    }

    static getPieceType(piece) {
        if (!piece) return null;
        return piece.split('_')[1];
    }

    static isValidPosition(x, y) {
        return x >= 0 && x < 9 && y >= 0 && y < 10;
    }

    static isInPalace(x, y, color) {
        if (x < 3 || x > 5) return false;
        if (color === 'red') return y >= 7 && y <= 9;
        return y >= 0 && y <= 2;
    }

    _countPiecesBetween(x1, y1, x2, y2) {
        let count = 0;
        if (x1 === x2) {
            const [start, end] = y1 < y2 ? [y1, y2] : [y2, y1];
            for (let y = start + 1; y < end; y++) {
                if (this.board[y][x1]) count++;
            }
        } else if (y1 === y2) {
            const [start, end] = x1 < x2 ? [x1, x2] : [x2, x1];
            for (let x = start + 1; x < end; x++) {
                if (this.board[y1][x]) count++;
            }
        }
        return count;
    }

    /**
     * 客户端走法校验（仅校验走子规则，不校验将军/照面）。
     * 用于推演模式：允许推演任意符合走子规则的着法以探索局面。
     * 返回 true 表示该走法符合棋子运动规则。
     */
    is_valid_move(from_x, from_y, to_x, to_y) {
        if (!ChessGame.isValidPosition(from_x, from_y)) return false;
        if (!ChessGame.isValidPosition(to_x, to_y)) return false;
        const piece = this.board[from_y][from_x];
        if (!piece) return false;
        const color = ChessGame.getPieceColor(piece);
        const target = this.board[to_y][to_x];
        if (target && ChessGame.getPieceColor(target) === color) return false;
        if (from_x === to_x && from_y === to_y) return false;

        const pieceType = ChessGame.getPieceType(piece);
        switch (pieceType) {
            case '帅':
            case '将':
                return this._validateKing(from_x, from_y, to_x, to_y, color);
            case '仕':
            case '士':
                return this._validateAdvisor(from_x, from_y, to_x, to_y, color);
            case '相':
            case '象':
                return this._validateElephant(from_x, from_y, to_x, to_y, color);
            case '马':
                return this._validateHorse(from_x, from_y, to_x, to_y);
            case '車':
                return this._validateRook(from_x, from_y, to_x, to_y);
            case '炮':
                return this._validateCannon(from_x, from_y, to_x, to_y);
            case '兵':
            case '卒':
                return this._validatePawn(from_x, from_y, to_x, to_y, color);
            default:
                return false;
        }
    }

    _validateKing(from_x, from_y, to_x, to_y, color) {
        const dx = Math.abs(to_x - from_x);
        const dy = Math.abs(to_y - from_y);
        // 飞将吃帅：两王同列且中间无子
        if (dx === 0) {
            const target = this.board[to_y][to_x];
            if (target && ['帅', '将'].includes(ChessGame.getPieceType(target))) {
                return this._countPiecesBetween(from_x, from_y, to_x, to_y) === 0;
            }
        }
        if (!ChessGame.isInPalace(to_x, to_y, color)) return false;
        return (dx === 1 && dy === 0) || (dx === 0 && dy === 1);
    }

    _validateAdvisor(from_x, from_y, to_x, to_y, color) {
        if (!ChessGame.isInPalace(to_x, to_y, color)) return false;
        return Math.abs(to_x - from_x) === 1 && Math.abs(to_y - from_y) === 1;
    }

    _validateElephant(from_x, from_y, to_x, to_y, color) {
        if (Math.abs(to_x - from_x) !== 2 || Math.abs(to_y - from_y) !== 2) return false;
        const midX = (from_x + to_x) / 2;
        const midY = (from_y + to_y) / 2;
        if (this.board[midY][midX]) return false;
        if (color === 'red' && to_y < 5) return false;
        if (color === 'black' && to_y > 4) return false;
        return true;
    }

    _validateHorse(from_x, from_y, to_x, to_y) {
        const dx = Math.abs(to_x - from_x);
        const dy = Math.abs(to_y - from_y);
        if (!((dx === 1 && dy === 2) || (dx === 2 && dy === 1))) return false;
        const legX = dx === 2 ? (from_x + to_x) / 2 : from_x;
        const legY = dy === 2 ? (from_y + to_y) / 2 : from_y;
        return !this.board[legY][legX];
    }

    _validateRook(from_x, from_y, to_x, to_y) {
        if (from_x !== to_x && from_y !== to_y) return false;
        return this._countPiecesBetween(from_x, from_y, to_x, to_y) === 0;
    }

    _validateCannon(from_x, from_y, to_x, to_y) {
        if (from_x !== to_x && from_y !== to_y) return false;
        const between = this._countPiecesBetween(from_x, from_y, to_x, to_y);
        const target = this.board[to_y][to_x];
        if (!target) return between === 0;
        return between === 1;
    }

    _validatePawn(from_x, from_y, to_x, to_y, color) {
        const dx = to_x - from_x;
        const dy = to_y - from_y;
        if (color === 'red') {
            if (dy > 0) return false;
            if (from_y <= 4) {
                return (dx === 0 && dy === -1) || (Math.abs(dx) === 1 && dy === 0);
            }
            return dx === 0 && dy === -1;
        } else {
            if (dy < 0) return false;
            if (from_y >= 5) {
                return (dx === 0 && dy === 1) || (Math.abs(dx) === 1 && dy === 0);
            }
            return dx === 0 && dy === 1;
        }
    }

    /**
     * 获取某位置棋子的所有合法走法（用于推演高亮）。
     */
    get_valid_moves(x, y) {
        const moves = [];
        if (!this.board[y] || !this.board[y][x]) return moves;
        for (let ty = 0; ty < 10; ty++) {
            for (let tx = 0; tx < 9; tx++) {
                if (this.is_valid_move(x, y, tx, ty)) {
                    moves.push({ x: tx, y: ty });
                }
            }
        }
        return moves;
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

    /**
     * 推演专用走子：先校验走法规则再执行。返回是否成功。
     */
    make_validated_move(from_x, from_y, to_x, to_y) {
        if (!this.is_valid_move(from_x, from_y, to_x, to_y)) return false;
        return this.make_move(from_x, from_y, to_x, to_y);
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