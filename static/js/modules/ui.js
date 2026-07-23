/**
 * UI Module
 * Handles UI updates, event handling, and game state management
 */
import { renderPieces, renderClickAreas } from './board.js';
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
    importGame
} from './api.js';

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
 */
function updateHistoryList() {
    const historyList = document.getElementById('historyList');
    const history = gameState.moveHistory;

    if (!history || history.length === 0) {
        historyList.innerHTML = '<div class="history-empty">暂无记录</div>';
        return;
    }

    let html = '';
    for (let i = 0; i < history.length; i += 2) {
        const roundNum = Math.floor(i / 2) + 1;
        const redMove = history[i] ? history[i].description : '';
        const blackMove = history[i + 1] ? history[i + 1].description : '';
        html += `<div class="history-row">
            <span class="history-num">${roundNum}.</span>
            <span class="history-red">${redMove}</span>
            <span class="history-black">${blackMove}</span>
        </div>`;
    }
    historyList.innerHTML = html;
    historyList.scrollTop = historyList.scrollHeight;
}

/**
 * Main render function
 */
function render() {
    renderPieces(gameState.board, gameState.flipped, selectedPiece, validMoves);
    renderClickAreas(gameState.flipped, gameState.board, validMoves);
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

function handleExport() {
    const history = gameState.moveHistory;
    if (!history || history.length === 0) {
        showMessage('暂无走棋记录可导出', 'error');
        return;
    }

    const now = new Date();
    const dateStr = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;

    let content = `[游戏]中国象棋\n[日期]${dateStr}\n[结果]`;
    if (gameState.gameOver) {
        content += gameState.winner === 'draw' ? '和棋' : `${gameState.winner === 'red' ? '红方' : '黑方'}胜`;
    } else {
        content += '未结束';
    }
    content += '\n\n';

    for (let i = 0; i < history.length; i += 2) {
        const roundNum = Math.floor(i / 2) + 1;
        const redMove = history[i] ? history[i].description : '';
        const blackMove = history[i + 1] ? history[i + 1].description : '';
        content += `${roundNum}. ${redMove}\t${blackMove}\n`;
    }

    const saveData = {
        board: gameState.board,
        current_turn: gameState.currentTurn,
        move_history: gameState.moveHistory,
        game_over: gameState.gameOver,
        winner: gameState.winner,
        flipped: gameState.flipped
    };
    content += `\n--- DATA ---\n${JSON.stringify(saveData)}`;

    const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `象棋棋谱_${dateStr}.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    showMessage('棋谱已导出', 'success');
}

async function handleImport(file) {
    try {
        const text = await file.text();
        const dataMatch = text.match(/--- DATA ---\n([\s\S]*)$/);
        if (!dataMatch) {
            showMessage('文件格式不正确', 'error');
            return;
        }
        const saveData = JSON.parse(dataMatch[1].trim());
        const data = await importGame(saveData);

        if (data.success) {
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
            showMessage('棋谱已导入', 'success');
            render();
        } else {
            showMessage(data.message || '导入失败', 'error');
        }
    } catch (e) {
        showMessage('导入失败：文件格式错误', 'error');
    }
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

    document.getElementById('importBtn').addEventListener('click', () => {
        document.getElementById('importFile').click();
    });
    document.getElementById('importFile').addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (file) handleImport(file);
        e.target.value = '';
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
}

/**
 * Initialize the game
 */
function init() {
    initEventListeners();
    loadGameState();
}

export { init };