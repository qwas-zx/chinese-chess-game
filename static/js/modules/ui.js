/**
 * UI Module
 * Handles UI updates, event handling, and game state management
 */
import { renderPieces, renderClickAreas } from './board.js';
import { ChessGame, getMoveCoordinates } from './game_logic.js';
import {
    fetchGameState,
    fetchValidMoves,
    makeMove,
    resetGame,
    undoMove,
    flipBoard,
    resignGame,
    drawAction,
    adjustPiece,
    importGame,
    analyzeGame,
    reviewGame
} from './api.js';
import { openDeduce, resetToState, isActive as deduceActive } from './deduce.js';
import {
    boardToFen, fenToBoard,
    historyToPlainText, historyToPgn, pgnToMoves,
    exportBoardImage,
    buildSaveFileContent, parseSaveFile,
    downloadTextFile, copyToClipboard,
} from './io_formats.js';

// Game state
const gameState = {
    board: [],
    currentTurn: 'red',
    gameOver: false,
    winner: null,
    flipped: false,
    moveHistory: [],
    drawRequestedBy: null,
    adjustMode: false
};

// UI state
let selectedPiece = null;
let validMoves = [];
let adjustSelectedPieceType = null;

// History review state: 0 = initial board, k = after k moves,
// moveHistory.length = live/current. When < moveHistory.length the board
// shows the historical position instead of the live one.
let reviewStep = 0;

function isReviewing() {
    return reviewStep < (gameState.moveHistory ? gameState.moveHistory.length : 0);
}

/** Reconstruct the board after `reviewStep` moves from the move history. */
function getReviewBoard() {
    const g = new ChessGame();
    for (let i = 0; i < reviewStep; i++) {
        const move = gameState.moveHistory[i];
        const coords = getMoveCoordinates(move);
        if (!coords) continue;
        g.make_move(coords.from_x, coords.from_y, coords.to_x, coords.to_y);
    }
    return g.board;
}

/** Jump to a step in the move history and re-render. */
function navigateHistory(step) {
    const total = gameState.moveHistory ? gameState.moveHistory.length : 0;
    reviewStep = Math.max(0, Math.min(step, total));
    selectedPiece = null;
    validMoves = [];
    render();
}

/**
 * Show message to user
 */
function showMessage(text, type = '') {
    const messageEl = document.getElementById('message');
    messageEl.textContent = text;
    messageEl.className = 'message ' + type;
    if (type) {
        setTimeout(() => {
            if (messageEl.textContent === text) {
                messageEl.className = 'message';
            }
        }, 2500);
    }
}

/**
 * Update turn display
 */
function updateTurnDisplay() {
    const currentTurnEl = document.getElementById('currentTurn');
    if (gameState.gameOver) {
        if (gameState.winner === 'draw') {
            currentTurnEl.textContent = '和棋';
            currentTurnEl.className = '';
            currentTurnEl.style.color = '#b0b0b0';
        } else {
            const winnerText = gameState.winner === 'red' ? '红方' : '黑方';
            currentTurnEl.textContent = `${winnerText}获胜！`;
            currentTurnEl.className = gameState.winner === 'red' ? 'turn-red' : 'turn-black';
        }
        return;
    }
    currentTurnEl.style.color = '';
    const turnText = gameState.currentTurn === 'red' ? '红方' : '黑方';
    currentTurnEl.textContent = turnText;
    currentTurnEl.className = gameState.currentTurn === 'red' ? 'turn-red' : 'turn-black';
}

/**
 * Update draw request banner
 */
function updateDrawBanner() {
    const drawBanner = document.getElementById('drawBanner');
    const drawBannerText = document.getElementById('drawBannerText');
    const acceptDrawBtn = document.getElementById('acceptDrawBtn');
    const declineDrawBtn = document.getElementById('declineDrawBtn');

    if (gameState.drawRequestedBy && !gameState.gameOver) {
        const requester = gameState.drawRequestedBy === 'red' ? '红方' : '黑方';
        const responder = gameState.drawRequestedBy === 'red' ? '黑方' : '红方';
        drawBannerText.textContent = `${requester}请求求和，${responder}请回应`;
        acceptDrawBtn.style.display = 'inline-block';
        declineDrawBtn.style.display = 'inline-block';
        drawBanner.style.display = 'flex';
    } else {
        drawBanner.style.display = 'none';
    }
}

/**
 * Update move history list
 *
 * Each move cell is clickable: clicking jumps the board to the state
 * after that move. The currently-viewed step is highlighted.
 * reviewStep semantics: 0 = initial board, k = after k moves,
 * moveHistory.length = live/current.
 */
function updateHistoryList() {
    const historyList = document.getElementById('historyList');
    const history = gameState.moveHistory;
    const posEl = document.getElementById('histPosition');
    const total = history ? history.length : 0;

    if (posEl) posEl.textContent = `${reviewStep} / ${total}`;

    if (!history || history.length === 0) {
        historyList.innerHTML = '<div class="history-empty">暂无记录</div>';
        updateHistoryNavButtons();
        return;
    }

    let html = '';
    for (let i = 0; i < history.length; i += 2) {
        const roundNum = Math.floor(i / 2) + 1;
        const redMove = history[i] ? history[i].description : '';
        const blackMove = history[i + 1] ? history[i + 1].description : '';
        const redCurrent = reviewStep === i + 1;
        const blackCurrent = reviewStep === i + 2;
        html += `<div class="history-row">
            <span class="history-num">${roundNum}.</span>
            <span class="history-move history-red ${redCurrent ? 'history-current' : ''}" data-step="${i + 1}">${redMove}</span>
            <span class="history-move history-black ${blackCurrent ? 'history-current' : ''}" data-step="${i + 2}">${blackMove}</span>
        </div>`;
    }
    historyList.innerHTML = html;

    historyList.querySelectorAll('.history-move[data-step]').forEach(el => {
        el.addEventListener('click', () => {
            navigateHistory(parseInt(el.dataset.step, 10));
        });
    });

    const currentEl = historyList.querySelector('.history-current');
    if (currentEl) currentEl.scrollIntoView({ block: 'nearest' });

    updateHistoryNavButtons();
}

/** Enable/disable the prev/next nav buttons based on current review step. */
function updateHistoryNavButtons() {
    const total = gameState.moveHistory ? gameState.moveHistory.length : 0;
    const atStart = reviewStep <= 0;
    const atEnd = reviewStep >= total;
    const set = (id, disabled) => {
        const el = document.getElementById(id);
        if (el) el.disabled = disabled;
    };
    set('histFirstBtn', atStart);
    set('histPrevBtn', atStart);
    set('histNextBtn', atEnd);
    set('histLastBtn', atEnd);
}

/**
 * Main render function
 */
function render() {
    const reviewing = isReviewing();
    const board = reviewing ? getReviewBoard() : gameState.board;
    const lastMove = reviewing
        ? (reviewStep > 0 ? gameState.moveHistory[reviewStep - 1] : null)
        : (gameState.moveHistory.length > 0 ? gameState.moveHistory[gameState.moveHistory.length - 1] : null);
    renderPieces(board, gameState.flipped, reviewing ? null : selectedPiece, reviewing ? [] : validMoves, lastMove);
    renderClickAreas(gameState.flipped, board, reviewing ? [] : validMoves, lastMove);
    updateTurnDisplay();
    updateDrawBanner();
    updateHistoryList();

    const adjustBtn = document.getElementById('adjustBtn');
    const adjustPanel = document.getElementById('adjustPanel');
    const flipBtn = document.getElementById('flipBtn');

    if (gameState.adjustMode) {
        adjustBtn.classList.add('active');
        adjustPanel.style.display = 'block';
    } else {
        adjustBtn.classList.remove('active');
        adjustPanel.style.display = 'none';
        adjustSelectedPieceType = null;
        document.querySelectorAll('.adjust-piece').forEach(el => el.classList.remove('selected'));
    }

    if (gameState.flipped) {
        flipBtn.classList.add('active');
    } else {
        flipBtn.classList.remove('active');
    }

    // Visual cue when reviewing a past position
    const boardContainer = document.getElementById('boardContainer');
    if (boardContainer) boardContainer.classList.toggle('reviewing', reviewing);
}

/**
 * Load initial game state
 */
async function loadGameState() {
    try {
        const data = await fetchGameState();
        gameState.board = data.board;
        gameState.currentTurn = data.current_turn;
        gameState.gameOver = data.game_over;
        gameState.winner = data.winner;
        gameState.flipped = data.flipped;
        gameState.moveHistory = data.move_history || [];
        gameState.drawRequestedBy = data.draw_requested_by;
        gameState.adjustMode = data.adjust_mode;
        reviewStep = gameState.moveHistory.length;
        render();
    } catch (e) {
        showMessage('获取游戏状态失败', 'error');
    }
}

// ========== Event Handlers ==========

async function handleBoardClick(evt) {
    const target = evt.target.closest('.click-area');
    if (!target) return;

    const x = parseInt(target.dataset.x);
    const y = parseInt(target.dataset.y);
    if (isNaN(x) || isNaN(y)) return;

    if (gameState.adjustMode) {
        handleAdjustClick(x, y);
        return;
    }

    if (isReviewing()) {
        showMessage('正在回顾中，请先回到当前局面（点击 ⏭）', 'warning');
        return;
    }

    if (gameState.gameOver) return;

    const piece = gameState.board[y][x];

    if (selectedPiece) {
        const isValidMove = validMoves.some(m => m.x === x && m.y === y);

        if (isValidMove) {
            await handleMove(selectedPiece.x, selectedPiece.y, x, y);
            return;
        }

        if (piece) {
            const pieceColor = piece.startsWith('red_') ? 'red' : 'black';
            if (pieceColor === gameState.currentTurn) {
                selectedPiece = { x, y };
                const data = await fetchValidMoves(x, y);
                validMoves = data.success ? data.moves : [];
                render();
                return;
            }
        }

        selectedPiece = null;
        validMoves = [];
        render();
    } else {
        if (piece) {
            const pieceColor = piece.startsWith('red_') ? 'red' : 'black';
            if (pieceColor === gameState.currentTurn) {
                selectedPiece = { x, y };
                const data = await fetchValidMoves(x, y);
                validMoves = data.success ? data.moves : [];
                render();
            } else {
                showMessage('不是你的回合', 'error');
            }
        }
    }
}

async function handleMove(fromX, fromY, toX, toY) {
    const data = await makeMove(fromX, fromY, toX, toY);
    if (data.success) {
        gameState.board = data.board;
        gameState.currentTurn = data.current_turn;
        gameState.gameOver = data.game_over;
        gameState.winner = data.winner;
        gameState.moveHistory = data.move_history || [];
        gameState.drawRequestedBy = null;

        selectedPiece = null;
        validMoves = [];
        reviewStep = gameState.moveHistory.length;

        if (data.game_over) {
            if (data.winner === 'draw') {
                showMessage('和棋！', 'success');
            } else {
                const winnerText = data.winner === 'red' ? '红方' : '黑方';
                showMessage(`游戏结束！${winnerText}获胜！`, 'success');
            }
        } else if (data.message) {
            showMessage(data.message, 'warning');
        }
        render();
    } else {
        showMessage(data.message || '移动失败', 'error');
    }
}

async function handleAdjustClick(x, y) {
    const piece = gameState.board[y][x];

    if (piece) {
        const data = await adjustPiece('remove', x, y);
        if (data.success) {
            gameState.board = data.board;
            render();
        } else {
            showMessage(data.message || '操作失败', 'error');
        }
        return;
    }

    if (adjustSelectedPieceType) {
        const data = await adjustPiece('add', x, y, adjustSelectedPieceType);
        if (data.success) {
            gameState.board = data.board;
            render();
        } else {
            showMessage(data.message || '操作失败', 'error');
        }
    } else {
        showMessage('请先选择要添加的棋子', 'error');
    }
}

async function handleReset() {
    const data = await resetGame();
    if (data.success) {
        gameState.board = data.board;
        gameState.currentTurn = data.current_turn;
        gameState.gameOver = data.game_over;
        gameState.winner = data.winner;
        gameState.flipped = data.flipped;
        gameState.moveHistory = data.move_history || [];
        gameState.drawRequestedBy = null;
        gameState.adjustMode = false;
        selectedPiece = null;
        validMoves = [];
        reviewStep = gameState.moveHistory.length;
        showMessage('游戏已重置');
        render();
    }
}

async function handleUndo() {
    const data = await undoMove();
    if (data.success) {
        gameState.board = data.board;
        gameState.currentTurn = data.current_turn;
        gameState.gameOver = data.game_over;
        gameState.winner = data.winner;
        gameState.moveHistory = data.move_history || [];
        gameState.drawRequestedBy = null;
        selectedPiece = null;
        validMoves = [];
        reviewStep = gameState.moveHistory.length;
        showMessage('已悔棋');
        render();
    } else {
        showMessage(data.message || '悔棋失败', 'error');
    }
}

async function handleFlip() {
    const data = await flipBoard();
    if (data.success) {
        gameState.flipped = data.flipped;
        selectedPiece = null;
        validMoves = [];
        render();
    }
}

async function handleResign() {
    if (gameState.gameOver) return;
    if (!confirm('确定认输吗？')) return;

    const data = await resignGame();
    if (data.success) {
        gameState.gameOver = data.game_over;
        gameState.winner = data.winner;
        const winnerText = data.winner === 'red' ? '红方' : '黑方';
        showMessage(`${winnerText}获胜！对方认输`, 'success');
        render();
    }
}

async function handleDrawRequest() {
    if (gameState.gameOver) return;

    const data = await drawAction('request');
    if (data.success) {
        if (data.draw_accepted) {
            gameState.gameOver = true;
            gameState.winner = 'draw';
            gameState.drawRequestedBy = null;
            showMessage('和棋！双方同意', 'success');
        } else {
            gameState.drawRequestedBy = data.requested_by;
            showMessage(data.message, '');
        }
        render();
    } else {
        showMessage(data.message || '求和失败', 'error');
    }
}

async function handleDrawResponse(accept) {
    const data = await drawAction(accept ? 'accept' : 'decline');
    if (data.success) {
        if (accept && data.draw_accepted) {
            gameState.gameOver = true;
            gameState.winner = 'draw';
            gameState.drawRequestedBy = null;
            showMessage('和棋！双方同意', 'success');
        } else {
            gameState.drawRequestedBy = null;
            showMessage(data.message || '求和已拒绝', '');
        }
        render();
    } else {
        showMessage(data.message, 'error');
    }
}

async function handleToggleAdjust() {
    const data = await adjustPiece('toggle_mode');
    if (data.success) {
        gameState.adjustMode = data.adjust_mode;
        selectedPiece = null;
        validMoves = [];
        showMessage(gameState.adjustMode ? '已进入调整模式' : '已退出调整模式', '');
        render();
    }
}

// ========== Import / Export panel ==========
//
// One panel handles all four interchange formats (FEN / TXT / PGN / PNG)
// plus the legacy save-file format. Modes: 'export' (read-only preview +
// download/copy) and 'import' (paste or upload, then send to /api/import).

const IO_FORMATS = {
    export: [
        { id: 'fen',  label: 'FEN 局面', ext: 'fen', mime: 'text/plain;charset=utf-8' },
        { id: 'txt',  label: 'TXT 棋谱', ext: 'txt', mime: 'text/plain;charset=utf-8' },
        { id: 'pgn',  label: 'PGN',      ext: 'pgn', mime: 'application/x-chess-pgn' },
        { id: 'png',  label: 'PNG 图片', ext: 'png', mime: 'image/png' },
        { id: 'save', label: '存档',      ext: 'txt', mime: 'text/plain;charset=utf-8' },
    ],
    import: [
        { id: 'fen',  label: 'FEN 局面' },
        { id: 'pgn',  label: 'PGN'      },
        { id: 'save', label: '存档'      },
    ],
};

const ioState = {
    mode: 'export',
    format: 'fen',
};

function getIoEls() {
    return {
        panel:   document.getElementById('ioPanel'),
        title:   document.getElementById('ioTitle'),
        text:    document.getElementById('ioText'),
        chips:   document.getElementById('ioFormatChips'),
        hint:    document.getElementById('ioHint'),
        primary: document.getElementById('ioPrimaryBtn'),
        copy:    document.getElementById('ioCopyBtn'),
        fileLbl: document.getElementById('ioFileLabel'),
        fileIn:  document.getElementById('ioFileInput'),
    };
}

function openIoPanel(mode) {
    ioState.mode = mode;
    if (!IO_FORMATS[mode].some(f => f.id === ioState.format)) {
        ioState.format = IO_FORMATS[mode][0].id;
    }
    const els = getIoEls();
    els.title.textContent = mode === 'export' ? '导出' : '导入';
    els.panel.style.display = 'block';
    renderIoPanel();
}

function closeIoPanel() {
    const { panel } = getIoEls();
    if (panel) panel.style.display = 'none';
}

function renderIoPanel() {
    const els = getIoEls();
    const formats = IO_FORMATS[ioState.mode];
    els.chips.innerHTML = formats.map(f =>
        `<span class="io-chip ${f.id === ioState.format ? 'active' : ''}" data-io-format="${f.id}">${f.label}</span>`
    ).join('');
    els.chips.querySelectorAll('.io-chip').forEach(el => {
        el.addEventListener('click', () => {
            ioState.format = el.dataset.ioFormat;
            renderIoPanel();
        });
    });

    els.hint.textContent = '';
    els.hint.className = 'io-hint';

    if (ioState.mode === 'export') renderExportView();
    else renderImportView();
}

function renderExportView() {
    const els = getIoEls();
    els.fileLbl.style.display = 'none';
    els.copy.style.display = 'inline-block';

    const fmt = ioState.format;

    if (fmt === 'png') {
        els.text.value = '点击下方"下载"按钮，将当前棋盘渲染为 630×700 的 PNG 图片。';
        els.text.readOnly = true;
        els.primary.textContent = '下载 PNG';
        els.primary.style.display = 'inline-block';
        els.hint.textContent = '当前棋盘（含翻转视角）将渲染为高清图片。';
        return;
    }

    let content = '';
    let desc = '';
    if (fmt === 'fen') {
        content = boardToFen(gameState.board, gameState.currentTurn);
        desc = 'FEN 只保存当前局面，不含走棋记录。可在任意支持 FEN 的象棋软件中继续对局。';
    } else if (fmt === 'txt') {
        content = historyToPlainText(gameState.moveHistory, gameState.gameOver, gameState.winner);
        desc = '纯中文棋谱，可直接粘贴到聊天工具分享。';
    } else if (fmt === 'pgn') {
        content = historyToPgn(gameState.moveHistory, gameState.gameOver, gameState.winner);
        desc = 'PGN 格式，包含走棋记录与对局结果，国际通用。';
    } else if (fmt === 'save') {
        const built = buildSaveFileContent(
            gameState.board, gameState.currentTurn, gameState.moveHistory,
            gameState.gameOver, gameState.winner, gameState.flipped
        );
        content = built.content;
        desc = '完整存档（含棋盘 + 走棋历史），仅本系统可导入。';
    }
    els.text.value = content;
    els.text.readOnly = true;
    els.primary.textContent = '下载';
    els.primary.style.display = 'inline-block';
    els.hint.textContent = desc;
}

function renderImportView() {
    const els = getIoEls();
    els.text.value = '';
    els.text.readOnly = false;
    els.copy.style.display = 'none';
    els.primary.textContent = '导入';
    els.primary.style.display = 'inline-block';

    const fmt = ioState.format;
    if (fmt === 'save') {
        els.fileLbl.style.display = 'inline-block';
        els.text.placeholder = '可粘贴存档内容，或点击"选择文件"上传 .txt 存档…';
        els.hint.textContent = '存档格式：本系统导出的 .txt 文件（含 --- DATA --- 标记）。';
    } else if (fmt === 'fen') {
        els.fileLbl.style.display = 'none';
        els.text.placeholder = '粘贴 FEN 串，例如：\nrnbakabnr/9/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/1C5C1/9/RNBAKABNR w - - 0 1';
        els.hint.textContent = 'FEN：只导入局面，走棋历史会被清空。';
    } else if (fmt === 'pgn') {
        els.fileLbl.style.display = 'none';
        els.text.placeholder = '粘贴 PGN 内容，例如：\n[Event "中国象棋"]\n...\n1. b0c2 c9c7 2. ...';
        els.hint.textContent = 'PGN：从标准开局回放走法。如需自定义开局，请先用 FEN 模式导入。';
    }
}

async function handleIoPrimary() {
    if (ioState.mode === 'export') await doExport();
    else await doImport();
}

async function doExport() {
    const els = getIoEls();
    const fmt = ioState.format;

    if (fmt === 'png') {
        els.hint.textContent = '正在生成图片…';
        els.hint.className = 'io-hint';
        try {
            await exportBoardImage(gameState.board, gameState.flipped);
            els.hint.textContent = '图片已开始下载。';
            els.hint.className = 'io-hint io-success';
        } catch (e) {
            els.hint.textContent = '导出失败：' + (e.message || e);
            els.hint.className = 'io-hint io-error';
        }
        return;
    }

    const now = new Date();
    const dateStr = `${now.getFullYear()}${String(now.getMonth() + 1).padStart(2, '0')}${String(now.getDate()).padStart(2, '0')}`;
    const prefix = { fen: 'xiangqi_fen', txt: 'xiangqi_qipu', pgn: 'xiangqi', save: 'xiangqi_save' }[fmt] || 'xiangqi';
    const ext = IO_FORMATS.export.find(f => f.id === fmt).ext;
    const mime = IO_FORMATS.export.find(f => f.id === fmt).mime;
    const filename = `${prefix}_${dateStr}.${ext}`;
    downloadTextFile(els.text.value, filename, mime);
    els.hint.textContent = `已下载：${filename}`;
    els.hint.className = 'io-hint io-success';
}

async function doImport() {
    const els = getIoEls();
    const fmt = ioState.format;
    const raw = els.text.value.trim();

    if (!raw) {
        els.hint.textContent = '请先粘贴内容' + (fmt === 'save' ? '或选择文件' : '');
        els.hint.className = 'io-hint io-error';
        return;
    }

    let payload;
    try {
        if (fmt === 'fen') {
            fenToBoard(raw);  // local validation for nicer errors
            payload = { fen: raw };
        } else if (fmt === 'pgn') {
            const moves = pgnToMoves(raw);
            if (moves.length === 0) {
                throw new Error('未找到可识别的走法（应为 a-i + 数字 + a-i + 数字 格式，例如 b0c2）');
            }
            payload = { pgn: raw };
        } else if (fmt === 'save') {
            const parsed = parseSaveFile(raw);
            if (!parsed) throw new Error('未找到 --- DATA --- 标记，请使用本系统导出的存档');
            payload = parsed;
        }
    } catch (e) {
        els.hint.textContent = '解析失败：' + (e.message || e);
        els.hint.className = 'io-hint io-error';
        return;
    }

    els.hint.textContent = '导入中…';
    els.hint.className = 'io-hint';
    const data = await importGame(payload);
    if (data.success) {
        applyImportedState(data);
        els.hint.textContent = '导入成功';
        els.hint.className = 'io-hint io-success';
        setTimeout(closeIoPanel, 400);
    } else {
        els.hint.textContent = data.message || '导入失败';
        els.hint.className = 'io-hint io-error';
    }
}

function applyImportedState(data) {
    gameState.board = data.board;
    gameState.currentTurn = data.current_turn;
    gameState.moveHistory = data.move_history || [];
    gameState.gameOver = data.game_over;
    gameState.winner = data.winner;
    gameState.flipped = data.flipped;
    gameState.drawRequestedBy = null;
    gameState.adjustMode = false;
    selectedPiece = null;
    validMoves = [];
    reviewStep = gameState.moveHistory.length;
    showMessage('棋谱已导入', 'success');
    render();
}

async function handleIoFilePick(e) {
    const file = e.target.files[0];
    if (!file) return;
    try {
        const text = await file.text();
        const els = getIoEls();
        els.text.value = text;
        els.hint.textContent = `已读取：${file.name}`;
        els.hint.className = 'io-hint';
    } catch (_) {
        showMessage('读取文件失败', 'error');
    }
    e.target.value = '';
}

async function handleIoCopy() {
    const els = getIoEls();
    const ok = await copyToClipboard(els.text.value);
    if (ok) {
        els.hint.textContent = '已复制到剪贴板';
        els.hint.className = 'io-hint io-success';
    } else {
        els.hint.textContent = '复制失败，请手动选择并复制';
        els.hint.className = 'io-hint io-error';
    }
}

function handleExport() {
    openIoPanel('export');
}

function handleImport() {
    openIoPanel('import');
}

/**
 * Initialize all event listeners
 */
function initEventListeners() {
    document.getElementById('clickAreas').addEventListener('click', handleBoardClick);
    document.getElementById('resetBtn').addEventListener('click', handleReset);
    document.getElementById('flipBtn').addEventListener('click', handleFlip);
    document.getElementById('undoBtn').addEventListener('click', handleUndo);
    document.getElementById('drawBtn').addEventListener('click', handleDrawRequest);
    document.getElementById('resignBtn').addEventListener('click', handleResign);
    document.getElementById('adjustBtn').addEventListener('click', handleToggleAdjust);
    document.getElementById('exportBtn').addEventListener('click', handleExport);
    document.getElementById('acceptDrawBtn').addEventListener('click', () => handleDrawResponse(true));
    document.getElementById('declineDrawBtn').addEventListener('click', () => handleDrawResponse(false));

    // Import / Export panel
    document.getElementById('importBtn').addEventListener('click', handleImport);
    document.getElementById('closeIoBtn').addEventListener('click', closeIoPanel);
    document.getElementById('ioPrimaryBtn').addEventListener('click', handleIoPrimary);
    document.getElementById('ioCopyBtn').addEventListener('click', handleIoCopy);
    document.getElementById('ioFileInput').addEventListener('change', handleIoFilePick);
    document.querySelectorAll('.io-tab[data-io-mode]').forEach(el => {
        el.addEventListener('click', () => openIoPanel(el.dataset.ioMode));
    });

    document.querySelectorAll('.adjust-piece').forEach(el => {
        el.addEventListener('click', () => {
            document.querySelectorAll('.adjust-piece').forEach(e => e.classList.remove('selected'));
            el.classList.add('selected');
            adjustSelectedPieceType = el.dataset.piece;
        });
    });

    document.getElementById('historyToggle').addEventListener('click', () => {
        const historyList = document.getElementById('historyList');
        const historyArrow = document.getElementById('historyArrow');
        const isVisible = historyList.style.display !== 'none';
        historyList.style.display = isVisible ? 'none' : 'block';
        historyArrow.innerHTML = isVisible ? '&#9660;' : '&#9650;';
    });

    document.getElementById('histFirstBtn').addEventListener('click', () => navigateHistory(0));
    document.getElementById('histPrevBtn').addEventListener('click', () => navigateHistory(reviewStep - 1));
    document.getElementById('histNextBtn').addEventListener('click', () => navigateHistory(reviewStep + 1));
    document.getElementById('histLastBtn').addEventListener('click', () => navigateHistory(gameState.moveHistory.length));

    document.getElementById('analyzeBtn').addEventListener('click', handleAnalyze);
    document.getElementById('closeAnalyzeBtn').addEventListener('click', () => {
        document.getElementById('analyzePanel').style.display = 'none';
    });

    document.getElementById('reviewBtn').addEventListener('click', handleReview);
    document.getElementById('closeReviewBtn').addEventListener('click', () => {
        document.getElementById('reviewPanel').style.display = 'none';
    });

    document.getElementById('deduceBtn').addEventListener('click', handleDeduce);
    // On "reset to current", restore the deduce board from the real position
    document.addEventListener('deduce:reset-request', () => {
        resetToState(gameState.board, gameState.currentTurn, gameState.flipped);
    });
}

/**
 * Toggle deduce: copy the real position into the deduce board.
 */
function handleDeduce() {
    if (!gameState.board || gameState.board.length === 0) {
        showMessage('棋盘尚未加载', 'error');
        return;
    }
    if (deduceActive()) {
        // Re-sync to the current real position
        resetToState(gameState.board, gameState.currentTurn, gameState.flipped);
        showMessage('推演已同步到当前局势', '');
    } else {
        openDeduce(gameState.board, gameState.currentTurn, gameState.flipped);
        showMessage('推演模式已开启', '');
    }
}

async function handleAnalyze() {
    const panel = document.getElementById('analyzePanel');
    const loading = document.getElementById('analyzeLoading');
    const result = document.getElementById('analyzeResult');
    
    panel.style.display = 'block';
    loading.style.display = 'block';
    result.style.display = 'none';
    
    try {
        const data = await analyzeGame();
        if (data.success) {
            document.getElementById('analyzeDesc').textContent = data.recommendation.description;
            const score = data.evaluation;
            let scoreText = '平衡';
            if (score > 100) scoreText = `红方优势 (${score})`;
            else if (score < -100) scoreText = `黑方优势 (${score})`;
            document.getElementById('analyzeScore').textContent = scoreText;
            
            loading.style.display = 'none';
            result.style.display = 'block';
        } else {
            showMessage(data.message || '分析失败', 'error');
            panel.style.display = 'none';
        }
    } catch (e) {
        showMessage('分析失败', 'error');
        panel.style.display = 'none';
    }
}

async function handleReview() {
    const panel = document.getElementById('reviewPanel');
    const loading = document.getElementById('reviewLoading');
    const result = document.getElementById('reviewResult');
    
    panel.style.display = 'block';
    loading.style.display = 'block';
    result.style.display = 'none';
    
    try {
        const data = await reviewGame();
        if (data.success) {
            const reviews = data.reviews;
            let html = '';
            for (const review of reviews) {
                let qualityClass = '';
                let qualityText = '';
                switch (review.quality) {
                    case 'excellent': qualityClass = 'review-excellent'; qualityText = '精彩'; break;
                    case 'good': qualityClass = 'review-good'; qualityText = '合理'; break;
                    case 'miss': qualityClass = 'review-miss'; qualityText = '错失'; break;
                    case 'bad': qualityClass = 'review-bad'; qualityText = '较差'; break;
                }
                const colorText = review.color === 'red' ? '红' : '黑';
                html += `<div class="review-row">
                    <span class="review-num">${review.move_number}.</span>
                    <span class="review-color">${colorText}</span>
                    <span class="review-desc">${review.description}</span>
                    <span class="review-quality ${qualityClass}">${qualityText}</span>
                    <span class="review-comment">${review.comment}</span>
                </div>`;
            }
            document.getElementById('reviewList').innerHTML = html || '<div class="review-empty">暂无记录</div>';
            
            loading.style.display = 'none';
            result.style.display = 'block';
        } else {
            showMessage(data.message || '复盘失败', 'error');
            panel.style.display = 'none';
        }
    } catch (e) {
        showMessage('复盘失败', 'error');
        panel.style.display = 'none';
    }
}

/**
 * Initialize the game
 */
function init() {
    initEventListeners();
    loadGameState();
}

export { init };