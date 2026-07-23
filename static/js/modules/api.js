/**
 * API Module
 * Handles all backend HTTP communication: local game API + auth + online rooms.
 */

const API_BASE = '/api';

/**
 * Generic API request helper.
 * Tolerates non-JSON / non-2xx responses by returning a structured error.
 */
async function apiCall(endpoint, method = 'GET', data = null) {
    const options = { method, headers: {}, credentials: 'include' };
    if (data) {
        options.headers['Content-Type'] = 'application/json';
        options.body = JSON.stringify(data);
    }
    try {
        const response = await fetch(endpoint, options);
        const text = await response.text();
        let json = null;
        try { json = JSON.parse(text); } catch (_) { /* not json */ }
        if (json === null) {
            return { success: false, message: `请求失败 (${response.status})` };
        }
        return json;
    } catch (e) {
        return { success: false, message: '网络错误: ' + e.message };
    }
}

// ========== Local game API ==========

async function fetchGameState() {
    return apiCall('/api/state');
}

async function fetchValidMoves(x, y) {
    return apiCall('/api/valid_moves', 'POST', { x, y });
}

async function makeMove(fromX, fromY, toX, toY) {
    return apiCall('/api/move', 'POST', {
        from_x: fromX, from_y: fromY, to_x: toX, to_y: toY
    });
}

async function resetGame() {
    return apiCall('/api/reset', 'POST');
}

async function undoMove() {
    return apiCall('/api/undo', 'POST');
}

async function flipBoard() {
    return apiCall('/api/flip', 'POST');
}

async function resignGame() {
    return apiCall('/api/resign', 'POST');
}

async function drawAction(action) {
    return apiCall('/api/draw', 'POST', { action });
}

async function adjustPiece(action, x, y, piece) {
    return apiCall('/api/adjust', 'POST', { action, x, y, piece });
}

async function importGame(saveData) {
    return apiCall('/api/import', 'POST', saveData);
}

// ========== Auth API ==========

async function authRegister(username, password, redirect = '') {
    return apiCall('/auth/register', 'POST', { username, password, redirect });
}

async function authLogin(username, password, redirect = '') {
    return apiCall('/auth/login', 'POST', { username, password, redirect });
}

async function authLogout() {
    return apiCall('/auth/logout', 'POST');
}

async function authMe() {
    return apiCall('/auth/me', 'GET');
}

// ========== Online room API (control plane) ==========

async function createRoom() {
    return apiCall('/api/online/rooms', 'POST');
}

async function joinRoom(roomId) {
    return apiCall(`/api/online/rooms/${encodeURIComponent(roomId)}/join`, 'POST');
}

async function fetchRoom(roomId) {
    return apiCall(`/api/online/rooms/${encodeURIComponent(roomId)}`, 'GET');
}

async function leaveRoom(roomId) {
    return apiCall(`/api/online/rooms/${encodeURIComponent(roomId)}/leave`, 'POST');
}

async function fetchMyRoom() {
    return apiCall('/api/online/my-room', 'GET');
}

export {
    apiCall,
    // local
    fetchGameState, fetchValidMoves, makeMove,
    resetGame, undoMove, flipBoard, resignGame,
    drawAction, adjustPiece, importGame,
    // auth
    authRegister, authLogin, authLogout, authMe,
    // online rooms
    createRoom, joinRoom, fetchRoom, leaveRoom, fetchMyRoom,
};
