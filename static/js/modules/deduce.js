/**
 * Deduce module — floating panel for exploring moves without affecting the real board.
 *
 * Copies the current position into an independent ChessGame instance.
 * In online mode this is fully local (no socket messages, only self-visible).
 * Undo is implemented via a snapshot stack (board + turn + history) saved
 * before each move, so captured pieces are restored correctly.
 */
import { renderPieces, renderClickAreas } from './board.js';
import { ChessGame } from './game_logic.js';

// State
let deduceGame = null;          // ChessGame instance for the deduce board
let snapshots = [];             // Pre-move snapshot stack: {board, turn, history}
let selectedPiece = null;
let validMoves = [];
let flipped = false;
let active = false;
let originalFlipped = false;    // Flip state of the real board (deduce follows it)

// ---------- DOM ----------

/**
 * Build the deduce panel DOM dynamically (avoids modifying three HTML templates).
 */
function ensurePanel() {
    if (document.getElementById('deducePanel')) return;

    const panel = document.createElement('div');
    panel.id = 'deducePanel';
    panel.className = 'deduce-panel';
    panel.innerHTML = `
        <div class="deduce-header">
            <span class="deduce-title">推演模式</span>
            <span class="deduce-hint">仅本地可见，不影响真实棋盘</span>
            <button id="deduceCloseBtn" class="close-btn" title="关闭">×</button>
        </div>
        <div class="deduce-body">
            <div class="deduce-board-wrapper">
                <div class="deduce-board-container">
                    <img src="/static/assets/pieces/chessboard.png" alt="棋盘" class="board-image">
                    <div id="deducePiecesLayer" class="pieces-layer"></div>
                    <div id="deduceClickAreas" class="click-areas"></div>
                </div>
            </div>
            <div class="deduce-sidebar">
                <div class="deduce-turn">
                    推演回合：<span id="deduceTurn" class="turn-red">红方</span>
                </div>
                <div class="deduce-controls">
                    <button id="deduceUndoBtn" class="action-btn small" title="悔一步推演">推演悔棋</button>
                    <button id="deduceResetBtn" class="action-btn small" title="回到当前真实局势">回到当前</button>
                </div>
                <div class="deduce-history-header">推演记录</div>
                <div id="deduceHistoryList" class="deduce-history-list">
                    <div class="history-empty">暂无推演</div>
                </div>
            </div>
        </div>
    `;
    document.body.appendChild(panel);

    document.getElementById('deduceCloseBtn').addEventListener('click', closeDeduce);
    document.getElementById('deduceUndoBtn').addEventListener('click', undoDeduce);
    document.getElementById('deduceResetBtn').addEventListener('click', resetDeduce);
    document.getElementById('deduceClickAreas').addEventListener('click', handleDeduceClick);
}

// ---------- Render ----------

function renderDeduce() {
    if (!deduceGame) return;
    // game_logic.js stores move_history in flat from_x/to_x format;
    // renderPieces expects nested {from:{x,y}, to:{x,y}}.
    let lastMove = null;
    if (deduceGame.move_history.length > 0) {
        const raw = deduceGame.move_history[deduceGame.move_history.length - 1];
        lastMove = {
            from: { x: raw.from_x, y: raw.from_y },
            to: { x: raw.to_x, y: raw.to_y },
        };
    }
    renderPieces(deduceGame.board, flipped, selectedPiece, validMoves, lastMove, 'deducePiecesLayer');
    renderClickAreas(flipped, deduceGame.board, validMoves, lastMove, 'deduceClickAreas');

    const turnEl = document.getElementById('deduceTurn');
    if (turnEl) {
        const isRed = deduceGame.current_turn === 'red';
        turnEl.textContent = isRed ? '红方' : '黑方';
        turnEl.className = isRed ? 'turn-red' : 'turn-black';
    }

    const listEl = document.getElementById('deduceHistoryList');
    if (listEl) {
        const h = deduceGame.move_history;
        if (h.length === 0) {
            listEl.innerHTML = '<div class="history-empty">暂无推演</div>';
        } else {
            let html = '';
            for (let i = 0; i < h.length; i += 2) {
                const roundNum = Math.floor(i / 2) + 1;
                const redMove = h[i] ? h[i].description : '';
                const blackMove = h[i + 1] ? h[i + 1].description : '';
                html += `<div class="history-row">
                    <span class="history-num">${roundNum}.</span>
                    <span class="history-red">${redMove}</span>
                    <span class="history-black">${blackMove}</span>
                </div>`;
            }
            listEl.innerHTML = html;
            listEl.scrollTop = listEl.scrollHeight;
        }
    }
}

// ---------- Interaction ----------

function handleDeduceClick(evt) {
    if (!active || !deduceGame) return;
    const target = evt.target.closest('.click-area');
    if (!target) return;
    const x = parseInt(target.dataset.x);
    const y = parseInt(target.dataset.y);
    if (isNaN(x) || isNaN(y)) return;

    const piece = deduceGame.board[y][x];

    if (selectedPiece) {
        const isValid = validMoves.some(m => m.x === x && m.y === y);
        if (isValid) {
            // Save snapshot before moving (for deduce undo)
            snapshots.push({
                board: JSON.parse(JSON.stringify(deduceGame.board)),
                turn: deduceGame.current_turn,
                history: JSON.parse(JSON.stringify(deduceGame.move_history)),
            });
            deduceGame.make_validated_move(selectedPiece.x, selectedPiece.y, x, y);
            selectedPiece = null;
            validMoves = [];
            renderDeduce();
            return;
        }
        // Select another piece (either side — deduce ignores turn order)
        if (piece) {
            selectedPiece = { x, y };
            validMoves = deduceGame.get_valid_moves(x, y);
            renderDeduce();
            return;
        }
        // Deselect
        selectedPiece = null;
        validMoves = [];
        renderDeduce();
    } else {
        // In deduce mode, either side's pieces can be selected
        if (piece) {
            selectedPiece = { x, y };
            validMoves = deduceGame.get_valid_moves(x, y);
            renderDeduce();
        }
    }
}

// ---------- Control ----------

/**
 * Open deduce: copy the real position into the deduce board.
 * @param {Array} currentBoard - Real board 2D array
 * @param {string} currentTurn - 'red' | 'black'
 * @param {boolean} boardFlipped - Real board flip state
 */
function openDeduce(currentBoard, currentTurn, boardFlipped) {
    ensurePanel();
    deduceGame = new ChessGame();
    deduceGame.board = JSON.parse(JSON.stringify(currentBoard));
    deduceGame.current_turn = currentTurn || 'red';
    deduceGame.move_history = [];
    flipped = boardFlipped || false;
    originalFlipped = boardFlipped || false;
    snapshots = [];
    selectedPiece = null;
    validMoves = [];
    active = true;

    const panel = document.getElementById('deducePanel');
    panel.style.display = 'flex';
    renderDeduce();
}

function closeDeduce() {
    active = false;
    const panel = document.getElementById('deducePanel');
    if (panel) panel.style.display = 'none';
    selectedPiece = null;
    validMoves = [];
    snapshots = [];
}

/**
 * Undo: restore the previous state from the snapshot stack.
 */
function undoDeduce() {
    if (!deduceGame) return;
    if (snapshots.length === 0) {
        flashMessage('没有可悔的推演');
        return;
    }
    const snap = snapshots.pop();
    deduceGame.board = snap.board;
    deduceGame.current_turn = snap.turn;
    deduceGame.move_history = snap.history;
    selectedPiece = null;
    validMoves = [];
    renderDeduce();
}

/**
 * Reset to current: clear deduce history and restore the real position.
 * Dispatches an event so the host page can supply the latest real state.
 */
function resetDeduce() {
    if (!deduceGame) return;
    document.dispatchEvent(new CustomEvent('deduce:reset-request'));
}

/**
 * Internal reset: called by the host with the latest real position.
 */
function resetToState(currentBoard, currentTurn, boardFlipped) {
    if (!deduceGame) return;
    deduceGame.board = JSON.parse(JSON.stringify(currentBoard));
    deduceGame.current_turn = currentTurn || 'red';
    deduceGame.move_history = [];
    flipped = boardFlipped !== undefined ? boardFlipped : originalFlipped;
    snapshots = [];
    selectedPiece = null;
    validMoves = [];
    renderDeduce();
}

function isActive() {
    return active;
}

// Brief inline hint inside the deduce panel
function flashMessage(text) {
    const hint = document.querySelector('.deduce-hint');
    if (!hint) return;
    const prev = hint.textContent;
    hint.textContent = text;
    setTimeout(() => { hint.textContent = prev; }, 1500);
}

export { openDeduce, closeDeduce, undoDeduce, resetDeduce, resetToState, isActive };
