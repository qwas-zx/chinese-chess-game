/**
 * Online Module — SocketIO client + three-step protocol + play page UI.
 *
 * Mirrors the backend protocol in ws_routes.py:
 *   - State-changing ops (MOVE/RESIGN/DRAW star RESTART) are wrapped in
 *     {msg_id, room_id, type, seq, payload, timestamp}. The client sends,
 *     waits for ACK (3s timeout, 3 retries with the SAME msg_id so the
 *     server dedups). The server then broadcasts STATE_UPDATE.
 *   - STATE_UPDATE carries a FULL snapshot — the client OVERWRITES local
 *     state with it (server is the single source of truth).
 *   - Heartbeat: PING every 5s. On PONG, if current_seq > last_seq, the
 *     client requests CATCH_UP and overwrites with the returned snapshot.
 *   - On page load, the client fetches its current room from the server
 *     (HTTP /api/online/my-room) — the frontend holds no authoritative state.
 */
import { renderPieces, renderClickAreas } from './board.js';
import { ChessGame } from './game_logic.js';
import { fetchMyRoom, leaveRoom, authMe } from './api.js';
import { initNavUserInfo } from './auth_ui.js';

const socket = window.io({ transports: ['websocket'] });

// ----- online game state (authoritative copy mirrored from server) -----
const state = {
    roomId: null,
    myColor: null,            // 'red' | 'black'
    seq: 0,
    board: [],
    currentTurn: 'red',
    gameOver: false,
    winner: null,
    moveHistory: [],
    drawRequestedBy: null,
    flipped: false,
    status: 'waiting',
    players: {},
};

// ----- pending state-changing messages awaiting ACK -----
const pending = new Map();    // msg_id -> { msg, retries, timer }
const PENDING_TIMEOUT = 3000;
const PENDING_MAX_RETRIES = 3;

let heartbeatTimer = null;
let selectedPiece = null;
let validMoves = [];          // unused in online mode (server is authority)

// ---------- helpers ----------

function uuid() {
    if (crypto.randomUUID) return crypto.randomUUID();
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
        const r = Math.random() * 16 | 0;
        const v = c === 'x' ? r : (r & 0x3 | 0x8);
        return v.toString(16);
    });
}

function nowMs() { return Date.now(); }

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function buildMessage(type, payload = {}) {
    return {
        msg_id: uuid(),
        room_id: state.roomId,
        sender: state.myColor,        // informational only; server ignores
        type,
        seq: state.seq + 1,           // expected next seq
        payload,
        timestamp: nowMs(),
    };
}

function sendMessage(msg) {
    socket.emit('room_message', msg);
}

function trackPending(msg) {
    const entry = { msg, retries: 0, timer: null };
    const retry = () => {
        if (entry.retries >= PENDING_MAX_RETRIES) {
            pending.delete(msg.msg_id);
            showMessage('操作未确认，正在同步状态...', 'error');
            requestCatchUp();
            return;
        }
        entry.retries += 1;
        sendMessage(msg);             // same msg_id -> server dedups or applies
        entry.timer = setTimeout(retry, PENDING_TIMEOUT);
    };
    entry.timer = setTimeout(retry, PENDING_TIMEOUT);
    pending.set(msg.msg_id, entry);
    updatePendingIndicator();
}

function clearPending(msgId) {
    const entry = pending.get(msgId);
    if (entry) {
        if (entry.timer) clearTimeout(entry.timer);
        pending.delete(msgId);
        updatePendingIndicator();
    }
}

// ---------- high-level operations ----------

function sendMove(from, to) {
    const msg = buildMessage('MOVE', { from, to });
    trackPending(msg);
    sendMessage(msg);
    return msg.msg_id;
}

function sendResign() {
    const msg = buildMessage('RESIGN');
    trackPending(msg);
    sendMessage(msg);
}

function sendDrawRequest() {
    const msg = buildMessage('DRAW_REQUEST');
    trackPending(msg);
    sendMessage(msg);
}

function sendDrawAccept() {
    const msg = buildMessage('DRAW_ACCEPT');
    trackPending(msg);
    sendMessage(msg);
}

function sendDrawDecline() {
    const msg = buildMessage('DRAW_DECLINE');
    trackPending(msg);
    sendMessage(msg);
}

function sendRestart() {
    const msg = buildMessage('RESTART_REQUEST');
    trackPending(msg);
    sendMessage(msg);
}

function sendChat(text) {
    sendMessage({
        msg_id: uuid(), room_id: state.roomId, sender: state.myColor,
        type: 'CHAT', seq: null, payload: { text }, timestamp: nowMs(),
    });
}

function sendJoin() {
    sendMessage({
        msg_id: uuid(), room_id: state.roomId, sender: state.myColor,
        type: 'JOIN', seq: null, payload: {}, timestamp: nowMs(),
    });
}

function sendPing() {
    sendMessage({
        msg_id: uuid(), room_id: state.roomId, sender: state.myColor,
        type: 'PING', seq: null, payload: { last_seq: state.seq },
        timestamp: nowMs(),
    });
}

function requestCatchUp() {
    sendMessage({
        msg_id: uuid(), room_id: state.roomId, sender: state.myColor,
        type: 'CATCH_UP', seq: null, payload: { from_seq: state.seq },
        timestamp: nowMs(),
    });
}

// ---------- heartbeat ----------

function startHeartbeat() {
    stopHeartbeat();
    heartbeatTimer = setInterval(sendPing, 5000);
}

function stopHeartbeat() {
    if (heartbeatTimer) { clearInterval(heartbeatTimer); heartbeatTimer = null; }
}

// ---------- snapshot application (authoritative overwrite) ----------

function applySnapshot(snapshot) {
    if (!snapshot) return;
    if (snapshot.room_id) state.roomId = snapshot.room_id;
    if (typeof snapshot.seq === 'number') state.seq = snapshot.seq;
    if (snapshot.board) state.board = snapshot.board;
    if (snapshot.current_turn) state.currentTurn = snapshot.current_turn;
    state.gameOver = !!snapshot.game_over;
    state.winner = snapshot.winner;
    if (snapshot.move_history) state.moveHistory = snapshot.move_history;
    state.drawRequestedBy = snapshot.draw_requested_by;
    if (typeof snapshot.flipped === 'boolean') state.flipped = snapshot.flipped;
    if (snapshot.status) state.status = snapshot.status;
    if (snapshot.players) state.players = snapshot.players;
    render();
}

// ---------- rendering ----------

function showMessage(text, type = '') {
    const el = document.getElementById('message');
    if (!el) return;
    el.textContent = text;
    el.className = 'message ' + type;
    if (type) setTimeout(() => {
        if (el.textContent === text) el.className = 'message';
    }, 2500);
}

function updateTurnDisplay() {
    const el = document.getElementById('currentTurn');
    if (!el) return;
    if (state.gameOver) {
        if (state.winner === 'draw') {
            el.textContent = '和棋'; el.className = ''; el.style.color = '#b0b0b0';
        } else {
            const w = state.winner === 'red' ? '红方' : '黑方';
            el.textContent = `${w}获胜！`;
            el.className = state.winner === 'red' ? 'turn-red' : 'turn-black';
        }
        return;
    }
    el.style.color = '';
    const turn = state.currentTurn === 'red' ? '红方' : '黑方';
    const me = state.myColor && state.currentTurn === state.myColor ? '（你）' : '';
    el.textContent = turn + me;
    el.className = state.currentTurn === 'red' ? 'turn-red' : 'turn-black';
}

function updateDrawBanner() {
    const banner = document.getElementById('drawBanner');
    if (!banner) return;
    const txt = document.getElementById('drawBannerText');
    if (state.drawRequestedBy && !state.gameOver) {
        const requester = state.drawRequestedBy === 'red' ? '红方' : '黑方';
        txt.textContent = `${requester}请求求和，请回应`;
        banner.style.display = 'flex';
        const canRespond = state.myColor && state.drawRequestedBy !== state.myColor;
        document.getElementById('acceptDrawBtn').style.display = canRespond ? 'inline-block' : 'none';
        document.getElementById('declineDrawBtn').style.display = canRespond ? 'inline-block' : 'none';
    } else {
        banner.style.display = 'none';
    }
}

function updateHistoryList() {
    const list = document.getElementById('historyList');
    if (!list) return;
    const h = state.moveHistory;
    if (!h.length) { list.innerHTML = '<div class="history-empty">暂无记录</div>'; return; }
    let html = '';
    for (let i = 0; i < h.length; i += 2) {
        const n = Math.floor(i / 2) + 1;
        const r = h[i] ? h[i].description : '';
        const b = h[i + 1] ? h[i + 1].description : '';
        html += `<div class="history-row"><span class="history-num">${n}.</span><span class="history-red">${r}</span><span class="history-black">${b}</span></div>`;
    }
    list.innerHTML = html;
    list.scrollTop = list.scrollHeight;
}

function updateRoomInfo() {
    const el = document.getElementById('roomInfo');
    if (!el) return;
    const colorTxt = state.myColor === 'red' ? '红方' : (state.myColor === 'black' ? '黑方' : '—');
    let oppTxt = '等待对手加入...';
    if (state.myColor) {
        const opp = Object.values(state.players).find(p => p.color !== state.myColor);
        if (opp) oppTxt = `对手：${opp.username}${opp.connected ? '' : '（离线）'}`;
    }
    el.textContent = `房间号：${state.roomId || '—'} | 你执：${colorTxt} | ${oppTxt}`;
}

function updatePendingIndicator() {
    const el = document.getElementById('pendingIndicator');
    if (el) el.style.display = pending.size > 0 ? 'inline-block' : 'none';
}

function render() {
    const lastMove = state.moveHistory.length > 0 
        ? state.moveHistory[state.moveHistory.length - 1] 
        : null;
    renderPieces(state.board, state.flipped, selectedPiece, validMoves, lastMove);
    renderClickAreas(state.flipped, state.board, validMoves, lastMove);
    updateTurnDisplay();
    updateDrawBanner();
    updateHistoryList();
    updateRoomInfo();
    updatePendingIndicator();
}

// ---------- click handling (optimistic render + send) ----------

function handleBoardClick(evt) {
    const target = evt.target.closest('.click-area');
    if (!target) return;
    const x = parseInt(target.dataset.x);
    const y = parseInt(target.dataset.y);
    if (isNaN(x) || isNaN(y)) return;
    if (state.gameOver) return;
    if (state.status !== 'playing') { showMessage('对局尚未开始'); return; }
    if (!state.myColor) { showMessage('正在同步状态...'); return; }
    if (state.currentTurn !== state.myColor) {
        showMessage('不是你的回合', 'error'); return;
    }

    const piece = state.board[y] && state.board[y][x];
    const myPrefix = state.myColor === 'red' ? 'red_' : 'black_';

    if (selectedPiece) {
        // Deselect by clicking the same piece.
        if (selectedPiece.x === x && selectedPiece.y === y) {
            selectedPiece = null; render(); return;
        }
        // Select another of own pieces.
        if (piece && piece.startsWith(myPrefix)) {
            selectedPiece = { x, y }; render(); return;
        }
        // Attempt move to (x, y) — optimistic.
        const from = { x: selectedPiece.x, y: selectedPiece.y };
        const to = { x, y };
        const moving = state.board[from.y][from.x];
        state.board[to.y][to.x] = moving;
        state.board[from.y][from.x] = null;
        selectedPiece = null;
        render();
        sendMove(from, to);
        return;
    }
    if (piece) {
        if (piece.startsWith(myPrefix)) {
            selectedPiece = { x, y }; render();
        } else {
            showMessage('那是对方的棋子', 'error');
        }
    }
}

// ---------- socket event wiring ----------

function wireSocket() {
    socket.on('connect', () => {
        showMessage('已连接服务器', '');
        sendJoin();
        startHeartbeat();
    });

    socket.on('state_update', (data) => {
        // Authoritative overwrite.
        applySnapshot(data.snapshot);
    });

    socket.on('game_start', (data) => {
        state.status = 'playing';
        applySnapshot(data.snapshot);
        showMessage('对局开始！', 'success');
    });

    socket.on('game_over', (data) => {
        state.gameOver = true;
        state.winner = data.winner;
        if (data.snapshot) applySnapshot(data.snapshot);
        const myWin = data.winner === state.myColor;
        const txt = data.winner === 'draw' ? '和棋'
            : (myWin ? '你赢了！' : '你输了');
        showMessage(`游戏结束：${txt}`, myWin ? 'success' : 'warning');
    });

    socket.on('ack', (data) => {
        clearPending(data.msg_id);
    });

    socket.on('nack', (data) => {
        clearPending(data.msg_id);
        // Our optimistic update may be invalid -> resync.
        requestCatchUp();
        showMessage(data.reason || '操作被拒绝', 'error');
    });

    socket.on('pong', (data) => {
        const cur = (typeof data.current_seq === 'number') ? data.current_seq : state.seq;
        if (cur > state.seq) {
            // Missed updates while disconnected — catch up.
            requestCatchUp();
        } else {
            state.seq = cur;
        }
    });

    socket.on('catch_up_response', (data) => {
        applySnapshot(data.snapshot);
    });

    socket.on('player_left', (data) => {
        showMessage(`${data.username} 暂时离开`, 'warning');
        updateRoomInfo();
    });

    socket.on('chat', (data) => {
        const chatPanel = document.getElementById('chatPanel');
        const chatMessages = document.getElementById('chatMessages');
        const player = Object.values(state.players).find(p => p.color === data.sender);
        const name = player ? player.username : (data.sender === 'red' ? '红方' : '黑方');
        const isMe = data.sender === state.myColor;
        
        const msgDiv = document.createElement('div');
        msgDiv.className = `chat-message ${isMe ? 'chat-me' : 'chat-other'}`;
        msgDiv.innerHTML = `<span class="chat-name">${name}:</span><span class="chat-text">${escapeHtml(data.text)}</span>`;
        chatMessages.appendChild(msgDiv);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    });

    socket.on('force_disconnect', (data) => {
        showMessage(data.reason || '账号在其他地方登录', 'error');
        stopHeartbeat();
        socket.disconnect();
    });

    socket.on('disconnect', () => {
        showMessage('连接已断开，正在重连...', 'error');
        stopHeartbeat();
    });

    socket.on('error', (data) => {
        showMessage(data.reason || '服务器错误', 'error');
    });
}

// ---------- toolbar handlers ----------

async function handleLeave() {
    if (!confirm('确定离开房间吗？对局中离开将视为认输。')) return;
    stopHeartbeat();
    if (state.roomId) await leaveRoom(state.roomId);
    window.location.href = '/lobby';
}

function handleResign() {
    if (state.gameOver) return;
    if (!confirm('确定认输吗？')) return;
    sendResign();
}

function handleDrawRequest() {
    if (state.gameOver) return;
    sendDrawRequest();
    showMessage('已发送求和请求', '');
}

function handleDrawResponse(accept) {
    if (accept) sendDrawAccept(); else sendDrawDecline();
}

function handleFlipToggle() {
    state.flipped = !state.flipped;
    render();
}

let replayStep = 0;

function handleChat() {
    const panel = document.getElementById('chatPanel');
    panel.style.display = panel.style.display === 'none' ? 'block' : 'none';
}

function handleSendChat() {
    const input = document.getElementById('chatInput');
    const text = input.value.trim();
    if (text) {
        sendChat(text);
        input.value = '';
    }
}

function handleReplay() {
    const panel = document.getElementById('replayPanel');
    panel.style.display = 'block';
    replayStep = state.moveHistory.length;
    updateReplayUI();
}

function replayToStep(step) {
    const maxStep = state.moveHistory.length;
    replayStep = Math.max(0, Math.min(step, maxStep));
    updateReplayUI();
    
    const g = new ChessGame();
    for (let i = 0; i < replayStep; i++) {
        const move = state.moveHistory[i];
        g.make_move(move.from_x, move.from_y, move.to_x, move.to_y);
    }
    
    renderPieces(g.board, state.flipped, null, [], replayStep > 0 ? state.moveHistory[replayStep - 1] : null);
    renderClickAreas(state.flipped, g.board, [], replayStep > 0 ? state.moveHistory[replayStep - 1] : null);
}

function updateReplayUI() {
    const maxStep = state.moveHistory.length;
    document.getElementById('replayPosition').textContent = `${replayStep} / ${maxStep}`;
    
    let html = '';
    for (let i = 0; i < maxStep; i++) {
        const move = state.moveHistory[i];
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

async function initOnlineGame() {
    // Login check — kick to /login if not authenticated.
    const me = await authMe();
    if (!me.success) {
        window.location.href = '/login?redirect=' + encodeURIComponent('/play');
        return;
    }
    initNavUserInfo(me.user);

    wireSocket();

    document.getElementById('clickAreas').addEventListener('click', handleBoardClick);
    document.getElementById('leaveBtn').addEventListener('click', handleLeave);
    document.getElementById('resignBtn').addEventListener('click', handleResign);
    document.getElementById('drawBtn').addEventListener('click', handleDrawRequest);
    document.getElementById('acceptDrawBtn').addEventListener('click', () => handleDrawResponse(true));
    document.getElementById('declineDrawBtn').addEventListener('click', () => handleDrawResponse(false));
    document.getElementById('flipBtn').addEventListener('click', handleFlipToggle);
    document.getElementById('historyToggle').addEventListener('click', () => {
        const list = document.getElementById('historyList');
        const arrow = document.getElementById('historyArrow');
        const visible = list.style.display !== 'none';
        list.style.display = visible ? 'none' : 'block';
        arrow.innerHTML = visible ? '&#9660;' : '&#9650;';
    });

    document.getElementById('chatBtn').addEventListener('click', handleChat);
    document.getElementById('closeChatBtn').addEventListener('click', () => {
        document.getElementById('chatPanel').style.display = 'none';
    });
    document.getElementById('sendChatBtn').addEventListener('click', handleSendChat);
    document.getElementById('chatInput').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') handleSendChat();
    });

    document.getElementById('replayBtn').addEventListener('click', handleReplay);
    document.getElementById('closeReplayBtn').addEventListener('click', () => {
        document.getElementById('replayPanel').style.display = 'none';
    });
    document.getElementById('replayFirstBtn').addEventListener('click', () => replayToStep(0));
    document.getElementById('replayPrevBtn').addEventListener('click', () => replayToStep(replayStep - 1));
    document.getElementById('replayNextBtn').addEventListener('click', () => replayToStep(replayStep + 1));
    document.getElementById('replayLastBtn').addEventListener('click', () => replayToStep(state.moveHistory.length));

    // Recover authoritative state from server (page load / refresh).
    const mine = await fetchMyRoom();
    if (!mine.success || !mine.in_room) {
        showMessage('你不在任何房间，正在跳转大厅...', 'error');
        setTimeout(() => { window.location.href = '/lobby'; }, 1500);
        return;
    }
    state.roomId = mine.room_id;
    state.myColor = mine.color;
    applySnapshot(mine.snapshot);
    // Default flip so the player's own pieces sit at the bottom.
    state.flipped = (state.myColor === 'black');
    render();
}

initOnlineGame();
