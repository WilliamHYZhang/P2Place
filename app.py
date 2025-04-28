import math
import os, time, hmac, hashlib, base64
import random

import eventlet
eventlet.monkey_patch()

from dotenv import load_dotenv

from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit

load_dotenv()

# which overlay to serve (fullmesh vs kgossip)
MODE = os.environ.get('MODE', 'fullmesh')

# if set, compute k so that failure ≤ 10^(-nines) for N peers. If not set, NINES will be None.
nines_env = os.getenv('NINES')
NINES = int(nines_env) if nines_env else None

TURN_SECRET = bytes.fromhex(os.environ['TURN_SECRET'])
TURN_URLS   = os.environ['TURN_URLS'].split(',')

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')
app.config['MODE'] = MODE
app.config['NINES'] = NINES
app.config['TEMPLATES_AUTO_RELOAD'] = True

socketio = SocketIO(app, cors_allowed_origins="*")

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

# dict {'peer_id': 'socket_id'}
peers = {}

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

    if app.config['MODE'] == 'fullmesh':
        # tell the new client about all other peers
        emit('peers', { 'peers': list(peers.keys()) })
        # tell all other peers about the new client
        emit('peer-joined', { 'peerId': peer_id }, broadcast=True, include_self=False)
        peers[peer_id] = request.sid
    else:
        # k-gossip mode
        k = compute_k(len(peers), nines=app.config['NINES'])
        sample = random.sample(list(peers.keys()), k) if peers else []
        # tell the new client about the random sample of k clients
        emit('peers', { 'peers': sample })
        # tell those k clients about the new peer
        for pid in sample:
            emit('peer-joined', {'peerId': peer_id}, to=peers[pid])
        peers[peer_id] = request.sid  

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
    target = data['to']
    sid = peers.get(target)
    if sid:
        emit('signal', data, to=sid)

@socketio.on('disconnect')
def on_disconnect():
    """
    Clean up when a peer disconnects:
      - remove them from peers dict
      - notify remaining peers
    """
    gone = None
    for pid, sid in list(peers.items()):
        if sid == request.sid:
            gone = pid
            del peers[pid]
            break
    if gone:
        emit('peer-disconnected', { 'peerId': gone }, broadcast=True)

# Expose the WSGI application for Gunicorn
application = app

if __name__ == '__main__':
    # Local dev server with eventlet
    socketio.run(app, host='0.0.0.0', port=5000)
