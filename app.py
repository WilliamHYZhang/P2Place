from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit

app = Flask(__name__)
app.config['SECRET_KEY'] = 'replace-with-a-secure-key'
socketio = SocketIO(app, cors_allowed_origins="*")

# dict {'peer_id': 'socket_id'}
peers = {}

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('join')
def on_join(data):
    peer_id = data['peerId']
    peers[peer_id] = request.sid

    # Tell the newcomer who’s already here
    existing = [pid for pid in peers if pid != peer_id]
    emit('peers', { 'peers': existing })

    # Tell everyone else about the newcomer
    emit('peer-joined', { 'peerId': peer_id }, broadcast=True, include_self=False)

@socketio.on('signal')
def on_signal(data):
    # data = { to, from, signal }
    target = data['to']
    sid = peers.get(target)
    if sid:
        emit('signal', data, to=sid)

@socketio.on('disconnect')
def on_disconnect():
    # Find and remove the departing peer
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
