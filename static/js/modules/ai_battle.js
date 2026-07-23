/**
 * AI Battle Module
 *
 * Player (red) vs AI (black). The server handles AI move generation
 * automatically — every POST /api/ai/move returns the board AFTER the
 * AI has responded, so the client never needs to poll or wait.
 */
import { renderPieces, renderClickAreas } from './board.js';
import { ChessGame } from './game_logic.js';
import {
    fetchAiState,
    fetchAiValidMoves,
    makeAiMove,
    resetAiGame,
    setAiDifficulty,
    undoAiMove,
    resignAiGame,
    flipAiBoard,
    aiDraw,
    analyzeAiGame,
    reviewAiGame,
} from './api.js';

// ---------- game state ----------

const gameState = {
    board: [],
    currentTurn: 'red',
    gameOver: false,
    winner: null,
    flipped: false,
    moveHistory: [],
    difficulty: 'normal',
    playerColor: 'red',
    aiColor: 'black',
};

let selectedPiece = null;
let validMoves = [];
let aiThinking = false;

// ---------- UI helpers ----------

function showMessage(text, type = '') {
    const el = document.getElementById('message');
    if (!el) return;
    el.textContent = text;
    el.className = 'message ' + type;
    if (type) {
        setTimeout(() => {
            if (el.textContent === text) el.className = 'message';
        }, 2500);
    }
}

function setAiThinking(on, text) {
    aiThinking = on;
    const el = document.getElementById('aiThinking');
    if (!el) return;
    el.style.display = on ? 'flex' : 'none';
    if (on && text) {
        const t = document.getElementById('thinkingText');
        if (t) t.textContent = text;
    }
}

function updateTurnDisplay() {
    const el = document.getElementById('currentTurn');
    if (!el) return;
    if (gameState.gameOver) {
        if (gameState.winner === 'draw') {
            el.textContent = '和棋';
            el.className = '';
            el.style.color = '#b0b0b0';
        } else if (gameState.winner === 'red') {
            el.textContent = '你赢了！';
            el.className = 'turn-red';
            el.style.color = '';
        } else {
            el.textContent = 'AI 获胜';
            el.className = 'turn-black';
            el.style.color = '';
        }
        return;
    }
    el.style.color = '';
    if (gameState.currentTurn === 'red') {
        el.textContent = '你的回合';
        el.className = 'turn-red';
    } else {
        el.textContent = 'AI 回合';
        el.className = 'turn-black';
    }
}

function updateLastMove(data) {
    const info = document.getElementById('lastMoveInfo');
    if (!info) return;
    const playerEl = document.getElementById('lastPlayerMove');
    const aiEl = document.getElementById('lastAiMove');

    let hasInfo = false;
    if (data.player_move !== undefined) {
        if (playerEl) playerEl.textContent = data.player_move || '—';
        hasInfo = true;
    }
    if (data.ai_move !== undefined) {
        if (aiEl) aiEl.textContent = data.ai_move || '—';
        hasInfo = true;
    }
    info.style.display = hasInfo ? 'flex' : 'none';
}

function updateHistoryList() {
    const list = document.getElementById('historyList');
    if (!list) return;
    const history = gameState.moveHistory;
    if (!history || history.length === 0) {
        list.innerHTML = '<div class="history-empty">暂无记录</div>';
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
    list.innerHTML = html;
    list.scrollTop = list.scrollHeight;
}

function render() {
    const lastMove = gameState.moveHistory.length > 0 
        ? gameState.moveHistory[gameState.moveHistory.length - 1] 
        : null;
    renderPieces(gameState.board, gameState.flipped, selectedPiece, validMoves, lastMove);
    renderClickAreas(gameState.flipped, gameState.board, validMoves, lastMove);
    updateTurnDisplay();
    updateHistoryList();

    const flipBtn = document.getElementById('flipBtn');
    if (flipBtn) {
        flipBtn.classList.toggle('active', gameState.flipped);
    }
}

// ---------- state loading ----------

function applyState(data) {
    if (data.board) gameState.board = data.board;
    if (data.current_turn) gameState.currentTurn = data.current_turn;
    gameState.gameOver = !!data.game_over;
    gameState.winner = data.winner;
    if (typeof data.flipped === 'boolean') gameState.flipped = data.flipped;
    if (data.move_history) gameState.moveHistory = data.move_history;
    if (data.difficulty) gameState.difficulty = data.difficulty;
    if (data.player_color) gameState.playerColor = data.player_color;
    if (data.ai_color) gameState.aiColor = data.ai_color;
}

async function loadGameState() {
    const data = await fetchAiState();
    if (data.board) {
        applyState(data);
        // Sync difficulty dropdown
        const sel = document.getElementById('difficultySelect');
        if (sel && data.difficulty) sel.value = data.difficulty;
        render();
    } else {
        showMessage('获取游戏状态失败', 'error');
    }
}

// ---------- move handling ----------

async function handleBoardClick(evt) {
    const target = evt.target.closest('.click-area');
    if (!target) return;

    const x = parseInt(target.dataset.x);
    const y = parseInt(target.dataset.y);
    if (isNaN(x) || isNaN(y)) return;

    if (gameState.gameOver) return;
    if (gameState.currentTurn !== gameState.playerColor) {
        showMessage('请等待 AI 走棋', 'error');
        return;
    }
    if (aiThinking) return;

    const piece = gameState.board[y][x];

    if (selectedPiece) {
        const isValid = validMoves.some(m => m.x === x && m.y === y);
        if (isValid) {
            await handleMove(selectedPiece.x, selectedPiece.y, x, y);
            return;
        }
        // Reselect another own piece
        if (piece && piece.startsWith('red_')) {
            selectedPiece = { x, y };
            const data = await fetchAiValidMoves(x, y);
            validMoves = data.success ? data.moves : [];
            render();
            return;
        }
        // Deselect
        selectedPiece = null;
        validMoves = [];
        render();
    } else {
        if (piece && piece.startsWith('red_')) {
            selectedPiece = { x, y };
            const data = await fetchAiValidMoves(x, y);
            validMoves = data.success ? data.moves : [];
            if (!data.success) {
                showMessage(data.message || '无法获取走法', 'error');
            }
            render();
        } else if (piece) {
            showMessage('你只能移动红方棋子', 'error');
        }
    }
}

async function handleMove(fromX, fromY, toX, toY) {
    // Optimistic: show "AI thinking" immediately
    setAiThinking(true, 'AI 思考中…');
    selectedPiece = null;
    validMoves = [];

    const data = await makeAiMove(fromX, fromY, toX, toY);
    setAiThinking(false);

    if (data.success) {
        applyState(data);
        updateLastMove(data);
        render();

        if (data.game_over) {
            if (data.winner === 'red') {
                showMessage('你赢了！', 'success');
            } else if (data.winner === 'draw') {
                showMessage('和棋！', 'success');
            } else {
                showMessage('AI 获胜', 'warning');
            }
        } else if (data.check) {
            showMessage('将军！', 'warning');
        } else if (data.message) {
            showMessage(data.message, '');
        }
    } else {
        showMessage(data.message || '移动失败', 'error');
        // Reload state to stay in sync
        await loadGameState();
    }
}

// ---------- toolbar handlers ----------

async function handleReset() {
    setAiThinking(false);
    const data = await resetAiGame(gameState.difficulty);
    if (data.board) {
        applyState(data);
        selectedPiece = null;
        validMoves = [];
        showMessage('游戏已重置', 'success');
        render();
    } else {
        showMessage(data.message || '重置失败', 'error');
    }
}

async function handleUndo() {
    if (aiThinking) return;
    const data = await undoAiMove();
    if (data.success) {
        applyState(data);
        selectedPiece = null;
        validMoves = [];
        showMessage('已悔棋', '');
        render();
    } else {
        showMessage(data.message || '悔棋失败', 'error');
    }
}

async function handleFlip() {
    const data = await flipAiBoard();
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
    const data = await resignAiGame();
    if (data.success) {
        gameState.gameOver = true;
        gameState.winner = data.winner;
        showMessage('你认输了', 'warning');
        render();
    }
}

async function handleDraw() {
    if (gameState.gameOver) return;
    if (gameState.currentTurn !== gameState.playerColor) {
        showMessage('请等待 AI 走棋', 'error');
        return;
    }
    const data = await aiDraw();
    if (data.success) {
        showMessage(data.message, '');
    } else {
        showMessage(data.message || '求和失败', 'error');
    }
}

async function handleDifficultyChange(e) {
    const difficulty = e.target.value;
    const data = await setAiDifficulty(difficulty);
    if (data.board) {
        applyState(data);
        selectedPiece = null;
        validMoves = [];
        showMessage(`难度已切换为：${difficulty === 'easy' ? '简单' : difficulty === 'hard' ? '困难' : '普通'}，棋局已重置`, '');
        render();
    } else {
        showMessage(data.message || '切换难度失败', 'error');
        // Revert dropdown
        e.target.value = gameState.difficulty;
    }
}

let replayStep = 0;

async function handleAnalyze() {
    const panel = document.getElementById('analyzePanel');
    const loading = document.getElementById('analyzeLoading');
    const result = document.getElementById('analyzeResult');
    
    panel.style.display = 'block';
    loading.style.display = 'block';
    result.style.display = 'none';
    
    try {
        const data = await analyzeAiGame();
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
        const data = await reviewAiGame();
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

function handleReplay() {
    const panel = document.getElementById('replayPanel');
    panel.style.display = 'block';
    replayStep = gameState.moveHistory.length;
    updateReplayUI();
}

function replayToStep(step) {
    const maxStep = gameState.moveHistory.length;
    replayStep = Math.max(0, Math.min(step, maxStep));
    updateReplayUI();
    
    const g = new ChessGame();
    for (let i = 0; i < replayStep; i++) {
        const move = gameState.moveHistory[i];
        g.make_move(move.from_x, move.from_y, move.to_x, move.to_y);
    }
    
    renderPieces(g.board, gameState.flipped, null, [], replayStep > 0 ? gameState.moveHistory[replayStep - 1] : null);
    renderClickAreas(gameState.flipped, g.board, [], replayStep > 0 ? gameState.moveHistory[replayStep - 1] : null);
}

function updateReplayUI() {
    const maxStep = gameState.moveHistory.length;
    document.getElementById('replayPosition').textContent = `${replayStep} / ${maxStep}`;
    
    let html = '';
    for (let i = 0; i < maxStep; i++) {
        const move = gameState.moveHistory[i];
        const colorText = move.color === 'red' ? '红' : '黑';
        const isCurrent = i === replayStep - 1;
        html += `<div class="replay-row ${isCurrent ? 'replay-current' : ''}" data-step="${i + 1}" onclick="replayToStep(${i + 1})">
            <span class="replay-num">${i + 1}.</span>
            <span class="replay-color">${colorText}</span>
            <span class="replay-desc">${move.description}</span>
        </div>`;
    }
    document.getElementById('replayList').innerHTML = html || '<div class="replay-empty">暂无记录</div>';
}

// ---------- init ----------

function initEventListeners() {
    document.getElementById('clickAreas').addEventListener('click', handleBoardClick);
    document.getElementById('resetBtn').addEventListener('click', handleReset);
    document.getElementById('flipBtn').addEventListener('click', handleFlip);
    document.getElementById('undoBtn').addEventListener('click', handleUndo);
    document.getElementById('drawBtn').addEventListener('click', handleDraw);
    document.getElementById('resignBtn').addEventListener('click', handleResign);
    document.getElementById('difficultySelect').addEventListener('change', handleDifficultyChange);

    document.getElementById('historyToggle').addEventListener('click', () => {
        const list = document.getElementById('historyList');
        const arrow = document.getElementById('historyArrow');
        const visible = list.style.display !== 'none';
        list.style.display = visible ? 'none' : 'block';
        arrow.innerHTML = visible ? '&#9660;' : '&#9650;';
    });

    document.getElementById('analyzeBtn').addEventListener('click', handleAnalyze);
    document.getElementById('closeAnalyzeBtn').addEventListener('click', () => {
        document.getElementById('analyzePanel').style.display = 'none';
    });

    document.getElementById('reviewBtn').addEventListener('click', handleReview);
    document.getElementById('closeReviewBtn').addEventListener('click', () => {
        document.getElementById('reviewPanel').style.display = 'none';
    });

    document.getElementById('replayBtn').addEventListener('click', handleReplay);
    document.getElementById('closeReplayBtn').addEventListener('click', () => {
        document.getElementById('replayPanel').style.display = 'none';
    });

    document.getElementById('replayFirstBtn').addEventListener('click', () => replayToStep(0));
    document.getElementById('replayPrevBtn').addEventListener('click', () => replayToStep(replayStep - 1));
    document.getElementById('replayNextBtn').addEventListener('click', () => replayToStep(replayStep + 1));
    document.getElementById('replayLastBtn').addEventListener('click', () => replayToStep(gameState.moveHistory.length));
}

function initAiBattle() {
    initEventListeners();
    loadGameState();
}

export { initAiBattle };
