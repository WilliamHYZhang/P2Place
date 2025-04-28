import math
import os, time, hmac, hashlib, base64
import random
import redis

import eventlet
eventlet.monkey_patch()

from dotenv import load_dotenv

from flask import Flask, render_template, request, jsonify, session
from flask_socketio import SocketIO, emit, join_room

load_dotenv()

# which overlay to serve (fullmesh vs kgossip)
MODE = os.environ.get('MODE', 'fullmesh')

# if set, compute k so that failure ≤ 10^(-nines) for N peers. If not set, NINES will be None.
nines_env = os.getenv('NINES')
NINES = int(nines_env) if nines_env else None

TURN_SECRET = bytes.fromhex(os.environ['TURN_SECRET'])
TURN_URLS   = os.environ['TURN_URLS'].split(',')

# ----------------------------------------------------------------------------
# Redis setup (shared state + Socket.IO message queue)
# ----------------------------------------------------------------------------
REDIS_URL = os.environ.get('REDIS_URL')
redis_client = redis.from_url(REDIS_URL, decode_responses=True) if REDIS_URL else None
PEER_SET = 'peers'    # Redis set that holds all live peerIds across workers

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')
app.config['MODE'] = MODE
app.config['NINES'] = NINES
app.config['TEMPLATES_AUTO_RELOAD'] = True

# Redis pub/sub lets many Gunicorn workers share events transparently
socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    **({'message_queue': REDIS_URL} if REDIS_URL else {})
)

# -----------------------------------------------------------------------------
# Utility helpers
# -----------------------------------------------------------------------------

def compute_k(n_peers, nines):
    """
    Compute k for a one-shot k-out overlay so that failure ≤ 10^(-nines):
        k ≥ ln(n_peers) + nines * ln(10)

    Args:
        n_peers (int): total number of peers
        nines   (int|None): reliability in nines (e.g. 3 for 10^-3)

    Returns:
        int: the fan-out k, clamped to [1, n_peers]
    """
    # trivial cases
    if n_peers <= 1 or nines is None:
        return n_peers

    # static overlay formula
    k = math.ceil(math.log(n_peers) + nines * math.log(10))

    # can’t pick more than N peers
    return min(n_peers, max(1, k))

# -----------------------------------------------------------------------------
# HTTP endpoints
# -----------------------------------------------------------------------------

@app.route('/health')
def health():
    """Lightweight health-check endpoint for Render."""
    return "OK", 200

def make_turn_token(identity: str, ttl: int = 24*3600):
    username = f"{int(time.time()) + ttl}:{identity}"
    pwd = base64.b64encode(
        hmac.new(TURN_SECRET, username.encode(), hashlib.sha1).digest()
    ).decode()
    return {"username": username, "credential": pwd}

@app.route("/turn-token")
def turn_token():
    peer_id = request.args.get("id", "anon")
    return jsonify({
        "iceServers": [
            {"urls": "stun:stun.l.google.com:19302"},
            {"urls": TURN_URLS,
             "username": (t := make_turn_token(peer_id))["username"],
             "credential": t["credential"]}
        ]
    })

@app.route('/')
def index():
    """
    Render the main landing page.

    Returns:
        str: Rendered HTML of index.html.
    """
    return render_template('index.html', mode=app.config['MODE'])

# -----------------------------------------------------------------------------
# Socket.IO handlers
# -----------------------------------------------------------------------------

@socketio.on('join')
def on_join(data):
    """
    Handle a new peer joining the network.

    Depending on MODE, either:
      - fullmesh: broadcast the new peer to all peers, or
      - kgossip: send the new peer to a random sample of k peers.

    Args:
        data (dict): Must contain 'peerId' of the joining peer.
    """
    peer_id = data['peerId']

    # Persist peerId in the per‑socket session so we can retrieve it on disconnect
    session['peer_id'] = peer_id

    # Every client joins its own room (named by peerId) so we can
    # reliably address it across workers via Redis pub/sub.
    join_room(peer_id)

    # Add to the global live‑peer set (Redis)
    if redis_client:
        redis_client.sadd(PEER_SET, peer_id)
        all_peers = list(redis_client.smembers(PEER_SET))
        try:
            all_peers.remove(peer_id)
        except ValueError:
            pass
    else:
        # No Redis → assume single‑process dev session; no other peers.
        all_peers = []

    if app.config['MODE'] == 'fullmesh':
        # Tell the new client about all other peers
        emit('peers', {'peers': all_peers})
        # Broadcast the new peer to everyone else
        emit('peer-joined', {'peerId': peer_id}, broadcast=True, include_self=False)
    else:
        # k‑gossip mode
        k = compute_k(len(all_peers), nines=app.config['NINES'])
        sample = random.sample(all_peers, k) if all_peers else []
        emit('peers', {'peers': sample})
        for pid in sample:
            emit('peer-joined', {'peerId': peer_id}, room=pid)

@socketio.on('signal')
def on_signal(data):
    """
    Relay WebRTC signaling messages between peers.

    Args:
        data (dict): {
            'to': target peerId,
            'from': source peerId,
            'signal': SDP description or ICE candidate
        }
    """
    emit('signal', data, room=data['to'])

@socketio.on('disconnect')
def on_disconnect():
    """
    Clean up when a peer disconnects:
      - remove them from the Redis peer set
      - notify remaining peers
    """
    peer_id = session.get('peer_id')
    if not peer_id:
        return∂

    if redis_client:
        redis_client.srem(PEER_SET, peer_id)

    emit('peer-disconnected', {'peerId': peer_id}, broadcast=True)

# -----------------------------------------------------------------------------
# WSGI entrypoint (for Gunicorn) & local dev server
# -----------------------------------------------------------------------------

application = app

if __name__ == '__main__':
    # Local dev server with eventlet
    socketio.run(app, host='0.0.0.0', port=5000)
