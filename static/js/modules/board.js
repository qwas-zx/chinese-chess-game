/**
 * Board Rendering Module
 * Handles coordinate transformation and board rendering
 */

const BOARD_OFFSET_X = 55;
const BOARD_OFFSET_Y = 55;
const CELL_SIZE = 65;
const BOARD_WIDTH = 630;
const BOARD_HEIGHT = 700;

/**
 * Convert grid position to percentage for CSS positioning
 */
function gridToPercent(x, y, flipped) {
    let displayX = x, displayY = y;
    if (flipped) {
        displayX = 8 - x;
        displayY = 9 - y;
    }
    const px = BOARD_OFFSET_X + displayX * CELL_SIZE;
    const py = BOARD_OFFSET_Y + displayY * CELL_SIZE;
    return {
        xPercent: (px / BOARD_WIDTH) * 100,
        yPercent: (py / BOARD_HEIGHT) * 100
    };
}

/**
 * Get piece image URL
 */
function getPieceImageSrc(piece) {
    if (!piece) return null;
    return `/static/assets/pieces/${piece}.png`;
}

/**
 * Render all pieces on the board
 */
function renderPieces(board, flipped, selectedPiece, validMoves, lastMove) {
    const piecesLayer = document.getElementById('piecesLayer');
    piecesLayer.innerHTML = '';

    for (let y = 0; y < 10; y++) {
        for (let x = 0; x < 9; x++) {
            const piece = board[y][x];
            if (piece) {
                const { xPercent, yPercent } = gridToPercent(x, y, flipped);
                const img = document.createElement('img');
                img.src = getPieceImageSrc(piece);
                img.className = 'piece';
                img.dataset.x = x;
                img.dataset.y = y;

                if (selectedPiece && selectedPiece.x === x && selectedPiece.y === y) {
                    img.classList.add('selected');
                }

                const isCaptureTarget = validMoves.some(m => m.x === x && m.y === y);
                if (isCaptureTarget) {
                    img.classList.add('capture-highlight');
                }

                if (lastMove) {
                    if (lastMove.to.x === x && lastMove.to.y === y) {
                        img.classList.add('move-to');
                    }
                    if (lastMove.from.x === x && lastMove.from.y === y && !piece) {
                        img.classList.add('move-from');
                    }
                }

                img.style.left = xPercent + '%';
                img.style.top = yPercent + '%';
                piecesLayer.appendChild(img);
            }
        }
    }

    if (lastMove && !board[lastMove.from.y][lastMove.from.x]) {
        const { xPercent, yPercent } = gridToPercent(lastMove.from.x, lastMove.from.y, flipped);
        const marker = document.createElement('div');
        marker.className = 'move-from-marker';
        marker.style.left = xPercent + '%';
        marker.style.top = yPercent + '%';
        piecesLayer.appendChild(marker);
    }
}

/**
 * Render click areas for the board
 */
function renderClickAreas(flipped, board, validMoves, lastMove) {
    const clickAreas = document.getElementById('clickAreas');
    clickAreas.innerHTML = '';

    for (let y = 0; y < 10; y++) {
        for (let x = 0; x < 9; x++) {
            const { xPercent, yPercent } = gridToPercent(x, y, flipped);
            const area = document.createElement('div');
            area.className = 'click-area';
            area.dataset.x = x;
            area.dataset.y = y;

            area.style.left = xPercent + '%';
            area.style.top = yPercent + '%';

            const isValidMove = validMoves.some(m => m.x === x && m.y === y);
            if (isValidMove) {
                area.classList.add('valid-move');
                if (board[y][x]) {
                    area.classList.add('valid-capture');
                }
            }

            if (lastMove) {
                if (lastMove.from.x === x && lastMove.from.y === y) {
                    area.classList.add('last-move-from');
                }
                if (lastMove.to.x === x && lastMove.to.y === y) {
                    area.classList.add('last-move-to');
                }
            }

            clickAreas.appendChild(area);
        }
    }
}

export { gridToPercent, getPieceImageSrc, renderPieces, renderClickAreas };