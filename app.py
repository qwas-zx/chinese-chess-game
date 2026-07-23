"""
Chinese Chess Game - Application Entry Point

Supports two modes:
- Local two-player mode (original, HTTP API)
- Online multiplayer mode (SocketIO, room-based, three-step protocol)

Run:  python app.py   ->  http://127.0.0.1:5004
"""
import logging
import os

from flask import Flask
from flask_socketio import SocketIO

from logging_config import setup_logging

from db import init_db, close_db

from routes import (
    register_routes, register_ai_routes, register_auth_routes,
    register_room_routes, register_ws_handlers,
)

# Logging config (hardcoded)
setup_logging(level='DEBUG', logfile='logs/chinese-chess.log')
logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, 'templates'),
    static_folder=os.path.join(BASE_DIR, 'static'),
)
# Session secret. In production set CHESS_SECRET_KEY in the environment.
app.config['SECRET_KEY'] = os.environ.get('CHESS_SECRET_KEY', 'dev-secret-change-me')

# Auto-reload templates on file change (avoids stale template cache in
# non-debug mode — this is the "Flask cache" issue that required debug mode).
app.config['TEMPLATES_AUTO_RELOAD'] = True

# SocketIO with threading async mode — good enough for development and
# small-scale play without extra async-runtime dependencies.
socketio = SocketIO(app, async_mode='threading', cors_allowed_origins="*")

# Initialise the user database and tear down per-request connections.
init_db()
app.teardown_appcontext(close_db)

# Register all route groups.
register_routes(app)            # local game HTTP API
register_ai_routes(app)         # AI battle HTTP API
register_auth_routes(app)       # /auth/*
register_room_routes(app)       # /api/online/*
register_ws_handlers(socketio)  # SocketIO events

if __name__ == '__main__':
    # Debug mode can be enabled via CHESS_DEBUG=1 or CHESS_DEBUG=true
    debug_flag = os.environ.get('CHESS_DEBUG', '').lower() in ('1', 'true', 'yes')
    logger.info('=' * 50)
    logger.info('  中国象棋 - Chinese Chess Game')
    logger.info('  本地双人 + 线上联机 | Local & Online')
    logger.info('=' * 50)
    logger.info('  Server running at: http://127.0.0.1:5004')
    logger.info('=' * 50)
    socketio.run(app, debug=debug_flag, host='0.0.0.0', port=5004, allow_unsafe_werkzeug=True)
