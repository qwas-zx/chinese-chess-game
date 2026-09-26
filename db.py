"""
Chinese Chess Game - Database Layer

SQLite-backed user storage with werkzeug password hashing.
Provides per-request connection management via Flask's `g` object.

Schema:
- users(id, username, password_hash, is_admin, created_at)
- game_results(id, user_id, opponent_name, mode, result, played_at)
  mode  : 'ai' | 'online'
  result: 'win' | 'loss' | 'draw'
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
    """Create tables if not exist and run lightweight migrations.

    Called once at startup. Safe to call repeatedly (idempotent for the
    core schema). Migrations are best-effort ALTER TABLEs wrapped in
    try/except so existing DBs without the newer columns get upgraded.
    """
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                is_admin INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        # Migration: add is_admin column for older DBs created before this column.
        cols = {row[1] for row in conn.execute('PRAGMA table_info(users)')}
        if 'is_admin' not in cols:
            conn.execute('ALTER TABLE users ADD COLUMN is_admin INTEGER NOT NULL DEFAULT 0')

        conn.execute('''
            CREATE TABLE IF NOT EXISTS game_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                opponent_name TEXT,
                mode TEXT NOT NULL,
                result TEXT NOT NULL,
                played_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')
        # Index to speed up leaderboard / per-user stats queries.
        conn.execute(
            'CREATE INDEX IF NOT EXISTS idx_game_results_user_id '
            'ON game_results(user_id)'
        )

        # First registered user becomes the default administrator.
        has_admin = conn.execute(
            'SELECT 1 FROM users WHERE is_admin = 1 LIMIT 1'
        ).fetchone()
        if has_admin is None:
            first = conn.execute(
                'SELECT id FROM users ORDER BY id ASC LIMIT 1'
            ).fetchone()
            if first is not None:
                conn.execute(
                    'UPDATE users SET is_admin = 1 WHERE id = ?', (first[0],)
                )

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
    # First user in a fresh DB becomes admin.
    count = db.execute('SELECT COUNT(*) AS c FROM users').fetchone()['c']
    if count == 1:
        db.execute('UPDATE users SET is_admin = 1 WHERE id = ?', (cur.lastrowid,))
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


def is_admin(user_id):
    """True if the given user id has admin rights."""
    db = get_db()
    row = db.execute(
        'SELECT is_admin FROM users WHERE id = ?', (user_id,)
    ).fetchone()
    return bool(row and row['is_admin'])


# ========== Game result recording & stats ==========

def record_game_result(user_id, opponent_name, mode, result):
    """Insert a single game result row.

    - opponent_name: free text ('AI(简单)' / opponent username / None).
    - mode: 'ai' | 'online'
    - result: 'win' | 'loss' | 'draw'
    Silently ignored if user_id does not exist.
    """
    if result not in ('win', 'loss', 'draw'):
        return
    db = get_db()
    db.execute(
        'INSERT INTO game_results (user_id, opponent_name, mode, result) '
        'VALUES (?, ?, ?, ?)',
        (user_id, opponent_name, mode, result)
    )
    db.commit()


def get_user_stats(user_id):
    """Return {wins, losses, draws, total} for one user."""
    db = get_db()
    rows = db.execute(
        'SELECT result, COUNT(*) AS c FROM game_results '
        'WHERE user_id = ? GROUP BY result',
        (user_id,)
    ).fetchall()
    stats = {'wins': 0, 'losses': 0, 'draws': 0, 'total': 0}
    for r in rows:
        if r['result'] == 'win':
            stats['wins'] = r['c']
        elif r['result'] == 'loss':
            stats['losses'] = r['c']
        elif r['result'] == 'draw':
            stats['draws'] = r['c']
    stats['total'] = stats['wins'] + stats['losses'] + stats['draws']
    return stats


def get_leaderboard(limit=100):
    """Return leaderboard rows ordered by wins desc, then win-rate desc.

    Each row: {user_id, username, wins, losses, draws, total, win_rate}
    """
    db = get_db()
    rows = db.execute(
        '''
        SELECT
            u.id            AS user_id,
            u.username      AS username,
            COALESCE(SUM(CASE WHEN gr.result = 'win'  THEN 1 ELSE 0 END), 0) AS wins,
            COALESCE(SUM(CASE WHEN gr.result = 'loss' THEN 1 ELSE 0 END), 0) AS losses,
            COALESCE(SUM(CASE WHEN gr.result = 'draw' THEN 1 ELSE 0 END), 0) AS draws,
            COUNT(gr.id)    AS total
        FROM users u
        LEFT JOIN game_results gr ON gr.user_id = u.id
        GROUP BY u.id
        ORDER BY wins DESC, total DESC, u.id ASC
        LIMIT ?
        ''',
        (limit,)
    ).fetchall()
    out = []
    for r in rows:
        total = r['total']
        win_rate = (r['wins'] / total) if total else 0.0
        out.append({
            'user_id': r['user_id'],
            'username': r['username'],
            'wins': r['wins'],
            'losses': r['losses'],
            'draws': r['draws'],
            'total': total,
            'win_rate': round(win_rate * 100, 1),
        })
    return out


def get_all_users_with_stats():
    """All users plus their aggregate stats. Ordered by id asc."""
    db = get_db()
    rows = db.execute(
        '''
        SELECT
            u.id, u.username, u.is_admin, u.created_at,
            COALESCE(SUM(CASE WHEN gr.result = 'win'  THEN 1 ELSE 0 END), 0) AS wins,
            COALESCE(SUM(CASE WHEN gr.result = 'loss' THEN 1 ELSE 0 END), 0) AS losses,
            COALESCE(SUM(CASE WHEN gr.result = 'draw' THEN 1 ELSE 0 END), 0) AS draws,
            COUNT(gr.id) AS total
        FROM users u
        LEFT JOIN game_results gr ON gr.user_id = u.id
        GROUP BY u.id
        ORDER BY u.id ASC
        '''
    ).fetchall()
    out = []
    for r in rows:
        total = r['total']
        out.append({
            'id': r['id'],
            'username': r['username'],
            'is_admin': bool(r['is_admin']),
            'created_at': r['created_at'],
            'wins': r['wins'],
            'losses': r['losses'],
            'draws': r['draws'],
            'total': total,
            'win_rate': round((r['wins'] / total) * 100, 1) if total else 0.0,
        })
    return out


def get_game_records(limit=200):
    """Recent game records joined with username. Newest first."""
    db = get_db()
    rows = db.execute(
        '''
        SELECT gr.id, gr.user_id, u.username, gr.opponent_name,
               gr.mode, gr.result, gr.played_at
        FROM game_results gr
        LEFT JOIN users u ON u.id = gr.user_id
        ORDER BY gr.played_at DESC, gr.id DESC
        LIMIT ?
        ''',
        (limit,)
    ).fetchall()
    return [{
        'id': r['id'],
        'user_id': r['user_id'],
        'username': r['username'],
        'opponent_name': r['opponent_name'],
        'mode': r['mode'],
        'result': r['result'],
        'played_at': r['played_at'],
    } for r in rows]


def get_admin_stats():
    """High-level dashboard counters."""
    db = get_db()
    users = db.execute('SELECT COUNT(*) AS c FROM users').fetchone()['c']
    admins = db.execute(
        'SELECT COUNT(*) AS c FROM users WHERE is_admin = 1'
    ).fetchone()['c']
    games = db.execute('SELECT COUNT(*) AS c FROM game_results').fetchone()['c']
    wins = db.execute(
        "SELECT COUNT(*) AS c FROM game_results WHERE result = 'win'"
    ).fetchone()['c']
    return {
        'total_users': users,
        'total_admins': admins,
        'total_games': games,
        'total_wins': wins,
    }


def set_admin(user_id, is_admin_value):
    """Promote or demote a user. Returns False if user not found."""
    db = get_db()
    cur = db.execute(
        'UPDATE users SET is_admin = ? WHERE id = ?',
        (1 if is_admin_value else 0, user_id)
    )
    db.commit()
    return cur.rowcount > 0


def delete_user(user_id):
    """Delete a user and their game results. Returns False if not found."""
    db = get_db()
    cur = db.execute('DELETE FROM users WHERE id = ?', (user_id,))
    db.execute('DELETE FROM game_results WHERE user_id = ?', (user_id,))
    db.commit()
    return cur.rowcount > 0
