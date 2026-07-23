"""
Chinese Chess Game - Database Layer

SQLite-backed user storage with werkzeug password hashing.
Provides per-request connection management via Flask's `g` object.
"""
import os
import sqlite3
from flask import g
from werkzeug.security import generate_password_hash, check_password_hash

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'chess.db')


def get_db():
    """Get a per-request SQLite connection."""
    if 'db' not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute('PRAGMA foreign_keys = ON')
    return g.db


def close_db(_exc=None):
    """Close the per-request SQLite connection."""
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_db():
    """Create tables if not exist. Called once at startup."""
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
    finally:
        conn.close()


# ========== User operations ==========

def create_user(username, password):
    """Insert a new user. Raises sqlite3.IntegrityError if username exists."""
    db = get_db()
    pw_hash = generate_password_hash(password)
    cur = db.execute(
        'INSERT INTO users (username, password_hash) VALUES (?, ?)',
        (username, pw_hash)
    )
    db.commit()
    return cur.lastrowid


def get_user_by_username(username):
    db = get_db()
    return db.execute(
        'SELECT * FROM users WHERE username = ?', (username,)
    ).fetchone()


def get_user_by_id(user_id):
    db = get_db()
    return db.execute(
        'SELECT * FROM users WHERE id = ?', (user_id,)
    ).fetchone()


def verify_user(username, password):
    """Return user row if credentials valid, else None."""
    user = get_user_by_username(username)
    if user is None:
        return None
    if not check_password_hash(user['password_hash'], password):
        return None
    return user
