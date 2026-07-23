/**
 * 推演（Deduce）模块
 *
 * 在当前页面展开一个浮动小窗口，复制当前局势到独立棋盘，
 * 用户可自由走子推演，不影响真实棋盘。
 * 联机模式下完全本地进行，不发送任何 socket 消息，仅自己可见。
 *
 * 悔棋通过快照栈实现（每次走子前保存棋盘+回合深拷贝），
 * 以正确恢复被吃棋子。
 */
import { renderPieces, renderClickAreas } from './board.js';
import { ChessGame } from './game_logic.js';

// 推演状态
let deduceGame = null;          // 推演用 ChessGame 实例
let snapshots = [];             // 走子前的快照栈：{board, turn, history}
let selectedPiece = null;
let validMoves = [];
let flipped = false;
let active = false;
let originalFlipped = false;    // 真实棋盘的翻转状态（推演沿用）

// ---------- DOM 构建 ----------

/**
 * 动态构建推演面板 DOM（避免修改三个 HTML 模板）。
 * 面板包含：标题栏、小棋盘、控制按钮、推演记录。
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

    // 绑定事件
    document.getElementById('deduceCloseBtn').addEventListener('click', closeDeduce);
    document.getElementById('deduceUndoBtn').addEventListener('click', undoDeduce);
    document.getElementById('deduceResetBtn').addEventListener('click', resetDeduce);
    document.getElementById('deduceClickAreas').addEventListener('click', handleDeduceClick);
}

// ---------- 渲染 ----------

function renderDeduce() {
    if (!deduceGame) return;
    // game_logic.js 的 move_history 用 from_x/to_x 扁平格式，
    // 而 renderPieces 期望 {from:{x,y}, to:{x,y}} 嵌套格式，这里做转换。
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

    // 回合显示
    const turnEl = document.getElementById('deduceTurn');
    if (turnEl) {
        const isRed = deduceGame.current_turn === 'red';
        turnEl.textContent = isRed ? '红方' : '黑方';
        turnEl.className = isRed ? 'turn-red' : 'turn-black';
    }

    // 推演记录
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

// ---------- 交互 ----------

function handleDeduceClick(evt) {
    if (!active || !deduceGame) return;
    const target = evt.target.closest('.click-area');
    if (!target) return;
    const x = parseInt(target.dataset.x);
    const y = parseInt(target.dataset.y);
    if (isNaN(x) || isNaN(y)) return;

    const piece = deduceGame.board[y][x];

    if (selectedPiece) {
        // 走子
        const isValid = validMoves.some(m => m.x === x && m.y === y);
        if (isValid) {
            // 走子前保存快照（用于推演悔棋）
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
        // 选中其他棋子（任意方均可，推演不限制回合）
        if (piece) {
            selectedPiece = { x, y };
            validMoves = deduceGame.get_valid_moves(x, y);
            renderDeduce();
            return;
        }
        // 取消选中
        selectedPiece = null;
        validMoves = [];
        renderDeduce();
    } else {
        // 推演中可选中任意一方棋子
        if (piece) {
            selectedPiece = { x, y };
            validMoves = deduceGame.get_valid_moves(x, y);
            renderDeduce();
        }
    }
}

// ---------- 推演控制 ----------

/**
 * 开启推演：从真实局势复制初始状态。
 * @param {Array} currentBoard - 真实棋盘二维数组
 * @param {string} currentTurn - 'red' | 'black'
 * @param {boolean} boardFlipped - 真实棋盘翻转状态
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
 * 推演悔棋：从快照栈恢复上一步状态。
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
 * 回到当前：清空推演记录，重置为真实局势。
 * 需要调用方重新提供当前真实局势。
 */
function resetDeduce() {
    if (!deduceGame) return;
    // 触发自定义事件，让宿主页面重新提供当前局势
    document.dispatchEvent(new CustomEvent('deduce:reset-request'));
}

/**
 * 内部重置：由宿主调用，用最新真实局势重置推演棋盘。
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

// 简单提示（推演面板内）
function flashMessage(text) {
    const hint = document.querySelector('.deduce-hint');
    if (!hint) return;
    const prev = hint.textContent;
    hint.textContent = text;
    setTimeout(() => { hint.textContent = prev; }, 1500);
}

export { openDeduce, closeDeduce, undoDeduce, resetDeduce, resetToState, isActive };
