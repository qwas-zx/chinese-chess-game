"""Shared helper: persist an online room's game results to the DB.

Keeps the recording concern out of the Room class (which stays DB-agnostic).
``record_online_results`` reads ``room.build_results()`` (idempotent) and
writes one row per player.
"""
from db import record_game_result


def record_online_results(room):
    """Record both players' results for a finished online game, once."""
    if room is None:
        return
    for r in room.build_results():
        record_game_result(
            r['user_id'], r['opponent_name'], 'online', r['result']
        )
