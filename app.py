import math
import os
import random

from dotenv import load_dotenv

from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit

load_dotenv()

# which overlay to serve (fullmesh vs kgossip)
MODE = os.environ.get('MODE', 'fullmesh')

# if set, compute k so that failure ≤ 10^(-nines) for N peers. If not set, k will default to 3.
NINES = int(os.environ.get('NINES'))

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')
app.config['MODE'] = MODE
app.config['NINES'] = NINES
socketio = SocketIO(app, cors_allowed_origins="*")

def compute_k(n_peers, nines):
    """
    Compute the gossip fan-out parameter k.

    Ensures that the probability of failure over N peers is at most 10^(-nines):
        N^(2 - 2k) ≤ 10^(-nines)
    which yields k ≥ 1 + (nines * ln(10)) / (2 * ln(N)).

    Args:
        n_peers (int): Number of peers currently in the network.
        nines (int): The number of 9s of reliability required.

    Returns:
        int: The computed k, clamped to [0, n_peers].
    """
    print(n_peers, nines)
    if n_peers <= 1 or nines is None:
        return min(n_peers, 3)
    raw = math.ceil(1 + (nines * math.log(10)) / (2 * math.log(n_peers)))
    return min(n_peers, raw)

# dict {'peer_id': 'socket_id'}
peers = {}

@app.route('/')
def index():
    """
    Render the main landing page.

    Returns:
        str: Rendered HTML of index.html.
    """
    return render_template('index.html')

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
        sample = random.sample(list(peers.keys()), k)
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

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000)
