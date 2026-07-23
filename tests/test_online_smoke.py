"""
Online protocol smoke test.

Verifies the three-step protocol end-to-end against a running server:
  1. Two players register / login / get session cookies.
  2. Player A creates a room; player B joins -> both connect via SocketIO.
  3. GAME_START broadcast received by both.
  4. PING / PONG heartbeat.
  5. MOVE three-step: A sends MOVE -> ACK to A -> STATE_UPDATE to both.
  6. seq mismatch rejected (NACK).
  7. Wrong-turn rejected (NACK).
  8. msg_id dedup: re-send same msg_id -> ACK, no second broadcast.
  9. CATCH_UP returns the latest snapshot.

Run while `python app.py` is serving on http://127.0.0.1:5004.
"""
import json
import time
import uuid
import threading
import requests
import socketio

BASE = 'http://127.0.0.1:5004'
PREFIX = f't{int(time.time())}_'

results = []
def check(name, cond, extra=''):
    results.append((name, bool(cond), extra))
    print(f"[{'PASS' if cond else 'FAIL'}] {name} {extra}")


# ---- 1. register / login two players with separate cookie jars ----
sessA = requests.Session()
sessB = requests.Session()
unameA, unameB = PREFIX + 'red', PREFIX + 'black'

r = sessA.post(f'{BASE}/auth/register', json={'username': unameA, 'password': '1234'})
check('register A', r.json().get('success'), r.text[:120])
r = sessB.post(f'{BASE}/auth/register', json={'username': unameB, 'password': '1234'})
check('register B', r.json().get('success'), r.text[:120])

# Extract session cookie for SocketIO (flask-socketio uses the same session cookie)
cookieA = '; '.join(f'{k}={v}' for k, v in sessA.cookies.items())
cookieB = '; '.join(f'{k}={v}' for k, v in sessB.cookies.items())
check('session cookie A present', bool(cookieA), cookieA[:60])
check('session cookie B present', bool(cookieB), cookieB[:60])


# ---- 2. create + join room via HTTP control plane ----
r = sessA.post(f'{BASE}/api/online/rooms')
dataA = r.json()
check('create room', dataA.get('success'), f"room_id={dataA.get('room_id')}")
room_id = dataA['room_id']

r = sessB.post(f'{BASE}/api/online/rooms/{room_id}/join')
dataB = r.json()
check('join room', dataB.get('success') and dataB.get('color') == 'black',
      f"color={dataB.get('color')}")


# ---- 3. connect both via SocketIO with their session cookies ----
sioA = socketio.Client(logger=False, engineio_logger=False, reconnection=False)
sioB = socketio.Client(logger=False, engineio_logger=False, reconnection=False)

eventsA = {'game_start': None, 'state_update': [], 'ack': None, 'nack': None,
           'pong': None, 'catch_up_response': None, 'game_over': None,
           'force_disconnect': None, 'error': None}
eventsB = {'game_start': None, 'state_update': [], 'ack': None, 'nack': None,
           'pong': None, 'catch_up_response': None, 'game_over': None,
           'force_disconnect': None, 'error': None}

def _register(sio, ev, label):
    sio.on('game_start')(lambda d: (ev.update({'game_start': d}), print(f'  {label} <- game_start seq={d.get("seq")}')))
    sio.on('state_update')(lambda d: (ev['state_update'].append(d), print(f'  {label} <- state_update seq={d.get("seq")}')))
    sio.on('ack')(lambda d: (ev.update({'ack': d}), print(f'  {label} <- ack seq={d.get("current_seq")}')))
    sio.on('nack')(lambda d: (ev.update({'nack': d}), print(f'  {label} <- nack reason={d.get("reason")}')))
    sio.on('pong')(lambda d: (ev.update({'pong': d}), print(f'  {label} <- pong current_seq={d.get("current_seq")}')))
    sio.on('catch_up_response')(lambda d: (ev.update({'catch_up_response': d}), print(f'  {label} <- catch_up_response seq={d.get("seq")}')))
    sio.on('game_over')(lambda d: (ev.update({'game_over': d})))
    sio.on('force_disconnect')(lambda d: (ev.update({'force_disconnect': d})))
    sio.on('error')(lambda d: (ev.update({'error': d}), print(f'  {label} <- error {d}')))

_register(sioA, eventsA, 'A')
_register(sioB, eventsB, 'B')

sioA.connect(BASE, headers={'Cookie': cookieA}, transports=['polling'])
sioB.connect(BASE, headers={'Cookie': cookieB}, transports=['polling'])
time.sleep(0.5)
check('A connected', sioA.connected)
check('B connected', sioB.connected)

# Send JOIN so the server attaches us to the room explicitly.
def join_msg(room_id):
    return {'msg_id': str(uuid.uuid4()), 'room_id': room_id, 'sender': 'red',
            'type': 'JOIN', 'seq': None, 'payload': {}, 'timestamp': int(time.time() * 1000)}
sioA.emit('room_message', join_msg(room_id))
sioB.emit('room_message', join_msg(room_id))
time.sleep(0.6)

# Both should have received at least the initial state_update (snapshot on attach).
check('A got initial state_update', len(eventsA['state_update']) >= 1,
      f"count={len(eventsA['state_update'])}")
check('B got initial state_update', len(eventsB['state_update']) >= 1,
      f"count={len(eventsB['state_update'])}")
# And GAME_START (broadcast when room transitioned to PLAYING with 2 players).
check('A got game_start', eventsA['game_start'] is not None)
check('B got game_start', eventsB['game_start'] is not None)


# ---- 4. PING / PONG heartbeat ----
sioA.emit('room_message', {
    'msg_id': str(uuid.uuid4()), 'room_id': room_id, 'sender': 'red',
    'type': 'PING', 'seq': None, 'payload': {'last_seq': 0},
    'timestamp': int(time.time() * 1000),
})
time.sleep(0.4)
check('A got pong', eventsA['pong'] is not None,
      f"current_seq={eventsA['pong'].get('current_seq') if eventsA['pong'] else None}")


# ---- 5. MOVE three-step: A (red) moves a cannon  -> ACK + broadcast ----
# Red cannon at (1,7) -> (1,4)  (i.e. 炮二平五 in Chinese notation)
clearA_su = len(eventsA['state_update'])
clearB_su = len(eventsB['state_update'])
eventsA['ack'] = None
eventsA['nack'] = None

move_msg = {
    'msg_id': str(uuid.uuid4()), 'room_id': room_id, 'sender': 'red',
    'type': 'MOVE', 'seq': 1,  # expected next seq
    'payload': {'from': {'x': 1, 'y': 7}, 'to': {'x': 1, 'y': 4}},
    'timestamp': int(time.time() * 1000),
}
sioA.emit('room_message', move_msg)
time.sleep(0.6)

check('A got ACK for valid MOVE', eventsA['ack'] is not None and eventsA['ack'].get('current_seq') == 1,
      f"ack={eventsA['ack']}")
check('A received broadcast STATE_UPDATE for MOVE',
      len(eventsA['state_update']) > clearA_su,
      f"new_updates={len(eventsA['state_update']) - clearA_su}")
check('B received broadcast STATE_UPDATE for MOVE',
      len(eventsB['state_update']) > clearB_su,
      f"new_updates={len(eventsB['state_update']) - clearB_su}")
# Turn should now be black.
latest_su = eventsB['state_update'][-1]
check('turn flipped to black after MOVE',
      latest_su['snapshot']['current_turn'] == 'black',
      f"turn={latest_su['snapshot']['current_turn']}")


# ---- 6. seq mismatch: A sends MOVE with seq=5 (should be 2) -> NACK ----
eventsA['nack'] = None
bad_seq_msg = {
    'msg_id': str(uuid.uuid4()), 'room_id': room_id, 'sender': 'red',
    'type': 'MOVE', 'seq': 5,
    'payload': {'from': {'x': 1, 'y': 4}, 'to': {'x': 1, 'y': 5}},
    'timestamp': int(time.time() * 1000),
}
# But it's not red's turn now — server checks seq first? Actually in apply_move
# the order is: dedup -> seq check -> turn check. So seq=5 (expected 2) -> NACK seq mismatch.
sioA.emit('room_message', bad_seq_msg)
time.sleep(0.4)
check('seq mismatch rejected with NACK',
      eventsA['nack'] is not None and 'seq' in (eventsA['nack'].get('reason') or ''),
      f"nack={eventsA['nack']}")


# ---- 7. wrong turn: A (red) tries to move again (now black's turn) seq=2 -> NACK ----
eventsA['nack'] = None
wrong_turn_msg = {
    'msg_id': str(uuid.uuid4()), 'room_id': room_id, 'sender': 'red',
    'type': 'MOVE', 'seq': 2,
    'payload': {'from': {'x': 1, 'y': 4}, 'to': {'x': 1, 'y': 5}},
    'timestamp': int(time.time() * 1000),
}
sioA.emit('room_message', wrong_turn_msg)
time.sleep(0.4)
check('wrong-turn MOVE rejected with NACK',
      eventsA['nack'] is not None and '回合' in (eventsA['nack'].get('reason') or ''),
      f"nack={eventsA['nack']}")


# ---- 8. msg_id dedup: resend the EXACT same msg_id as the successful move ----
clearA_su = len(eventsA['state_update'])
eventsA['ack'] = None
sioA.emit('room_message', move_msg)   # same msg_id, seq=1
time.sleep(0.5)
check('duplicate msg_id gets ACK (no error)',
      eventsA['ack'] is not None,
      f"ack={eventsA['ack']}")
check('duplicate msg_id does NOT trigger new broadcast',
      len(eventsA['state_update']) == clearA_su,
      f"new_updates={len(eventsA['state_update']) - clearA_su}")


# ---- 9. CATCH_UP: B requests catch-up from seq=0 -> gets latest snapshot ----
sioB.emit('room_message', {
    'msg_id': str(uuid.uuid4()), 'room_id': room_id, 'sender': 'black',
    'type': 'CATCH_UP', 'seq': None, 'payload': {'from_seq': 0},
    'timestamp': int(time.time() * 1000),
})
time.sleep(0.4)
check('B got catch_up_response with seq=1',
      eventsB['catch_up_response'] is not None and eventsB['catch_up_response'].get('seq') == 1,
      f"cu={eventsB['catch_up_response']}")


# ---- 10. Identity: B pretends to be "red" in the sender field -> still rejected on red's turn? ----
# After our MOVE, it's black's turn. B (black) sends a MOVE with sender='red' but B is actually black.
# Server reads identity from connection (B=black), so this is black's turn -> the move is LEGAL.
# This proves the server ignores msg.sender and uses connection identity.
# Use a valid black move: pawn at (0,3) -> (0,4) (one step forward, before river).
eventsB['ack'] = None
eventsB['nack'] = None
identity_msg = {
    'msg_id': str(uuid.uuid4()), 'room_id': room_id, 'sender': 'red',  # LIAR
    'type': 'MOVE', 'seq': 2,
    'payload': {'from': {'x': 0, 'y': 3}, 'to': {'x': 0, 'y': 4}},  # black pawn forward
    'timestamp': int(time.time() * 1000),
}
sioB.emit('room_message', identity_msg)
time.sleep(0.6)
check('B (black) move with lying sender=red accepted (identity from connection)',
      eventsB['ack'] is not None and eventsB['ack'].get('current_seq') == 2,
      f"ack={eventsB['ack']}")
check('current turn back to red after black move',
      eventsB['state_update'][-1]['snapshot']['current_turn'] == 'red')


# ---- cleanup ----
sioA.disconnect()
sioB.disconnect()
time.sleep(0.3)
sessA.post(f'{BASE}/api/online/rooms/{room_id}/leave')
sessB.post(f'{BASE}/api/online/rooms/{room_id}/leave')

print('\n' + '=' * 60)
passed = sum(1 for _, ok, _ in results if ok)
total = len(results)
print(f'Smoke test: {passed}/{total} passed')
for name, ok, extra in results:
    if not ok:
        print(f'  FAILED: {name}  {extra}')
print('=' * 60)
exit(0 if passed == total else 1)
