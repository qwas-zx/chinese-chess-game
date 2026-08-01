/**
 * IO Formats Module
 *
 * Encoding/decoding between game state and various import/export formats:
 *   - FEN  : Xiangqi position string (board + turn only, no history)
 *   - TXT  : Human-readable Chinese notation, one round per line
 *   - PGN  : Portable Game Notation with coordinate-style moves
 *   - PNG  : Render the current board to a downloadable image
 *
 * Piece letter convention matches the Python backend (game/io_formats.py):
 *   K/k = King, A/a = Advisor, B/b = Elephant, N/n = Horse,
 *   R/r = Rook, C/c = Cannon, P/p = Pawn
 * Uppercase = red, lowercase = black. Board layout: top row first (black
 * side), 9 columns wide — same as the in-memory 2D array.
 */

// ---------- Piece <-> letter ----------

const PIECE_TO_FEN = {
    'red_帅': 'K', 'red_仕': 'A', 'red_相': 'B', 'red_马': 'N',
    'red_車': 'R', 'red_炮': 'C', 'red_兵': 'P',
    'black_将': 'k', 'black_士': 'a', 'black_象': 'b', 'black_马': 'n',
    'black_車': 'r', 'black_炮': 'c', 'black_卒': 'p',
};
const FEN_TO_PIECE = Object.fromEntries(
    Object.entries(PIECE_TO_FEN).map(([p, l]) => [l, p])
);

const BOARD_WIDTH = 9;
const BOARD_HEIGHT = 10;

// ---------- FEN ----------

/**
 * Encode a board + turn into a FEN string.
 * @param {Array<Array<?string>>} board  10x9 grid, top row first (black side)
 * @param {'red'|'black'} currentTurn
 * @returns {string}
 */
export function boardToFen(board, currentTurn) {
    const rows = [];
    for (let y = 0; y < BOARD_HEIGHT; y++) {
        let row = '';
        let empty = 0;
        for (let x = 0; x < BOARD_WIDTH; x++) {
            const piece = board[y][x];
            if (piece) {
                if (empty > 0) { row += empty; empty = 0; }
                row += PIECE_TO_FEN[piece] || '?';
            } else {
                empty++;
            }
        }
        if (empty > 0) row += empty;
        rows.push(row);
    }
    const turn = currentTurn === 'black' ? 'b' : 'w';
    return `${rows.join('/')} ${turn} - - 0 1`;
}

/**
 * Parse a FEN string. Accepts full FEN or bare position field.
 * @param {string} fen
 * @returns {{board: Array<Array<?string>>, current_turn: 'red'|'black'}}
 * @throws {Error} on malformed input
 */
export function fenToBoard(fen) {
    const trimmed = (fen || '').trim();
    if (!trimmed) throw new Error('FEN 为空');
    const parts = trimmed.split(/\s+/);
    const rows = parts[0].split('/');
    if (rows.length !== BOARD_HEIGHT) {
        throw new Error(`FEN 需要 ${BOARD_HEIGHT} 行棋盘，得到 ${rows.length} 行`);
    }
    const board = Array.from({ length: BOARD_HEIGHT }, () => Array(BOARD_WIDTH).fill(null));
    for (let y = 0; y < BOARD_HEIGHT; y++) {
        let x = 0;
        for (const ch of rows[y]) {
            if (/\d/.test(ch)) {
                x += parseInt(ch, 10);
            } else {
                const piece = FEN_TO_PIECE[ch];
                if (!piece) throw new Error(`未知 FEN 字符: ${ch}`);
                if (x >= BOARD_WIDTH) throw new Error(`FEN 第 ${y + 1} 行宽度超过 ${BOARD_WIDTH}`);
                board[y][x] = piece;
                x++;
            }
        }
        if (x !== BOARD_WIDTH) throw new Error(`FEN 第 ${y + 1} 行宽度不足 ${BOARD_WIDTH}`);
    }
    const turn = (parts[1] && parts[1].toLowerCase() === 'b') ? 'black' : 'red';
    return { board, current_turn: turn };
}

// ---------- Plain-text notation ----------

/**
 * Render move history as plain Chinese notation, one round per line.
 * @param {Array} moveHistory
 * @param {boolean} gameOver
 * @param {?string} winner  'red' | 'black' | 'draw' | null
 * @returns {string}
 */
export function historyToPlainText(moveHistory, gameOver, winner) {
    const lines = [];
    if (gameOver) {
        if (winner === 'draw') lines.push('结果：和棋');
        else if (winner) lines.push(`结果：${winner === 'red' ? '红方' : '黑方'}胜`);
    }
    if (!moveHistory || moveHistory.length === 0) {
        lines.push('（暂无走棋记录）');
        return lines.join('\n');
    }
    for (let i = 0; i < moveHistory.length; i += 2) {
        const round = Math.floor(i / 2) + 1;
        const red = _moveDesc(moveHistory[i]);
        const black = moveHistory[i + 1] ? _moveDesc(moveHistory[i + 1]) : '';
        let line = `${round}. ${red}`;
        if (black) line += `\t${black}`;
        lines.push(line);
    }
    return lines.join('\n');
}

function _moveDesc(record) {
    if (!record) return '';
    if (record.description) return String(record.description);
    if (record.piece) {
        const p = String(record.piece);
        return p.includes('_') ? p.split('_')[1] : p;
    }
    return '';
}

// ---------- PGN ----------

/**
 * (x, y) -> PGN square id. Columns a-i (a = x=0), rows 0-9
 * (0 = red's back rank = y=9).
 */
function coordToSquare(x, y) {
    return String.fromCharCode(97 + x) + (9 - y);
}

function squareToCoord(sq) {
    if (!sq || sq.length < 2) throw new Error(`非法坐标: ${sq}`);
    const x = sq.charCodeAt(0) - 97;
    const y = 9 - parseInt(sq.slice(1), 10);
    if (x < 0 || x >= BOARD_WIDTH || y < 0 || y >= BOARD_HEIGHT) {
        throw new Error(`坐标超出棋盘: ${sq}`);
    }
    return { x, y };
}

/**
 * Generate a PGN string with coordinate-style moves.
 * @param {Array} moveHistory
 * @param {boolean} gameOver
 * @param {?string} winner
 * @param {{event?: string}} [meta]
 * @returns {string}
 */
export function historyToPgn(moveHistory, gameOver, winner, meta = {}) {
    let result = '*';
    if (gameOver) {
        if (winner === 'draw') result = '1/2-1/2';
        else if (winner === 'red') result = '1-0';
        else if (winner === 'black') result = '0-1';
    }
    const now = new Date();
    const dateStr = `${now.getFullYear()}.${String(now.getMonth() + 1).padStart(2, '0')}.${String(now.getDate()).padStart(2, '0')}`;
    const headers = [
        `[Event "${meta.event || '中国象棋'}"]`,
        '[Site "Local"]',
        `[Date "${dateStr}"]`,
        '[Variant "Xiangqi"]',
        `[Result "${result}"]`,
    ];

    const tokens = [];
    for (let i = 0; i < (moveHistory || []).length; i++) {
        const mv = moveHistory[i];
        const c = _extractCoords(mv);
        if (!c) continue;
        if (i % 2 === 0) tokens.push(`${Math.floor(i / 2) + 1}.`);
        tokens.push(coordToSquare(c.fx, c.fy) + coordToSquare(c.tx, c.ty));
    }
    tokens.push(result);
    return headers.join('\n') + '\n\n' + tokens.join(' ');
}

/**
 * Extract (from_x, from_y, to_x, to_y) from a move-history record,
 * tolerating both server (nested from/to) and frontend (flat from_x) shapes.
 */
function _extractCoords(record) {
    if (!record) return null;
    let fx, fy, tx, ty;
    if (record.from_x !== undefined) {
        fx = record.from_x; fy = record.from_y; tx = record.to_x; ty = record.to_y;
    } else if (record.from && record.to) {
        fx = record.from.x; fy = record.from.y; tx = record.to.x; ty = record.to.y;
    } else {
        return null;
    }
    if ([fx, fy, tx, ty].some(v => v === undefined || v === null)) return null;
    return { fx, fy, tx, ty };
}

/**
 * Extract coordinate moves from a PGN string.
 * Only coordinate-style moves (e.g. "b0c2") are recognised.
 * @param {string} pgn
 * @returns {Array<{from:{x,y}, to:{x,y}}>}
 */
export function pgnToMoves(pgn) {
    if (!pgn) return [];
    let cleaned = pgn.replace(/\[[^\]]*\]/g, ' ');
    cleaned = cleaned.replace(/\{[^}]*\}/g, ' ');
    cleaned = cleaned.replace(/;[^\n]*/g, ' ');
    const moves = [];
    const re = /([a-i])(\d)([a-i])(\d)/g;
    let m;
    while ((m = re.exec(cleaned)) !== null) {
        try {
            const from = squareToCoord(m[1] + m[2]);
            const to = squareToCoord(m[3] + m[4]);
            moves.push({ from, to });
        } catch (_) { /* skip invalid */ }
    }
    return moves;
}

// ---------- PNG image export ----------

// Board geometry — must match board.js
const BOARD_OFFSET_X = 55;
const BOARD_OFFSET_Y = 55;
const CELL_SIZE = 65;
const BOARD_PIXEL_WIDTH = 630;
const BOARD_PIXEL_HEIGHT = 700;

function loadImage(src) {
    return new Promise((resolve, reject) => {
        const img = new Image();
        img.onload = () => resolve(img);
        img.onerror = () => reject(new Error(`图片加载失败: ${src}`));
        img.src = src;
    });
}

/**
 * Render the current board (with pieces) to a PNG and trigger a download.
 * @param {Array<Array<?string>>} board
 * @param {boolean} flipped
 * @param {string} [filename]  defaults to chessboard_<date>.png
 * @returns {Promise<void>}
 */
export async function exportBoardImage(board, flipped, filename) {
    const canvas = document.createElement('canvas');
    canvas.width = BOARD_PIXEL_WIDTH;
    canvas.height = BOARD_PIXEL_HEIGHT;
    const ctx = canvas.getContext('2d');

    // Background first
    const bg = await loadImage('/static/assets/pieces/chessboard.png');
    ctx.drawImage(bg, 0, 0, BOARD_PIXEL_WIDTH, BOARD_PIXEL_HEIGHT);

    // Load every distinct piece image once, then draw.
    const piecePositions = [];
    for (let y = 0; y < BOARD_HEIGHT; y++) {
        for (let x = 0; x < BOARD_WIDTH; x++) {
            if (board[y][x]) piecePositions.push({ x, y, piece: board[y][x] });
        }
    }
    if (piecePositions.length > 0) {
        const distinctPieces = [...new Set(piecePositions.map(p => p.piece))];
        const images = await Promise.all(
            distinctPieces.map(p => loadImage(`/static/assets/pieces/${p}.png`))
        );
        const pieceImg = Object.fromEntries(distinctPieces.map((p, i) => [p, images[i]]));

        for (const pos of piecePositions) {
            const img = pieceImg[pos.piece];
            if (!img) continue;
            let dx = pos.x, dy = pos.y;
            if (flipped) { dx = 8 - pos.x; dy = 9 - pos.y; }
            const cx = BOARD_OFFSET_X + dx * CELL_SIZE;
            const cy = BOARD_OFFSET_Y + dy * CELL_SIZE;
            const size = CELL_SIZE; // piece fills roughly one cell
            ctx.drawImage(img, cx - size / 2, cy - size / 2, size, size);
        }
    }

    const now = new Date();
    const dateStr = `${now.getFullYear()}${String(now.getMonth() + 1).padStart(2, '0')}${String(now.getDate()).padStart(2, '0')}`;
    const name = filename || `chessboard_${dateStr}.png`;
    const url = canvas.toDataURL('image/png');
    const a = document.createElement('a');
    a.href = url;
    a.download = name;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
}

// ---------- Save-file format (existing JSON-embedded backup) ----------

/**
 * Build the legacy save-file content: human-readable header + "--- DATA ---"
 * + JSON blob. Kept for backward compatibility with previously exported
 * files and as the "full backup" option.
 */
export function buildSaveFileContent(board, currentTurn, moveHistory, gameOver, winner, flipped) {
    const now = new Date();
    const dateStr = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
    let content = `[游戏]中国象棋\n[日期]${dateStr}\n[结果]`;
    if (gameOver) {
        content += winner === 'draw' ? '和棋' : `${winner === 'red' ? '红方' : '黑方'}胜`;
    } else {
        content += '未结束';
    }
    content += '\n\n';
    for (let i = 0; i < (moveHistory || []).length; i += 2) {
        const round = Math.floor(i / 2) + 1;
        const red = moveHistory[i] ? _moveDesc(moveHistory[i]) : '';
        const black = moveHistory[i + 1] ? _moveDesc(moveHistory[i + 1]) : '';
        content += `${round}. ${red}\t${black}\n`;
    }
    const saveData = {
        board,
        current_turn: currentTurn,
        move_history: moveHistory,
        game_over: gameOver,
        winner,
        flipped,
    };
    content += `\n--- DATA ---\n${JSON.stringify(saveData)}`;
    return { content, filename: `象棋棋谱_${dateStr}.txt` };
}

/**
 * Parse a legacy save-file (the text format produced by buildSaveFileContent).
 * Returns the embedded JSON payload, or null if the file isn't a save file.
 */
export function parseSaveFile(text) {
    const m = text.match(/--- DATA ---\r?\n([\s\S]*)$/);
    if (!m) return null;
    return JSON.parse(m[1].trim());
}

// ---------- Generic file helpers ----------

export function downloadTextFile(content, filename, mime = 'text/plain;charset=utf-8') {
    const blob = new Blob([content], { type: mime });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

export async function copyToClipboard(text) {
    try {
        await navigator.clipboard.writeText(text);
        return true;
    } catch (_) {
        // Fallback for non-secure contexts
        const ta = document.createElement('textarea');
        ta.value = text;
        ta.style.position = 'fixed';
        ta.style.opacity = '0';
        document.body.appendChild(ta);
        ta.select();
        let ok = false;
        try { ok = document.execCommand('copy'); } catch (_) { ok = false; }
        document.body.removeChild(ta);
        return ok;
    }
}
