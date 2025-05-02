# P2Place 🧩🎨  
**Peer-to-peer collaborative pixel art inspired by r/place — fully decentralized, real-time, and serverless.**

![Screenshot](https://p2place.nyc3.cdn.digitaloceanspaces.com/p2place_meta.png)

P2Place is a WebRTC-powered, CRDT-synchronized pixel canvas where every user directly connects to others without relying on a central server. Paint pixels, create murals, and watch the world draw with you—all in your browser.

---

## 🚀 Features

- 🕸️ **Peer-to-peer overlay** — no central coordination  
- 📦 **WebRTC mesh and static k-gossip overlays**  
- 🎨 **Realtime CRDT sync of canvas state**  
- 🔧 **Lamport clock-based causal ordering**  
- 🌍 **TURN server support for NAT traversal**  
- 🧪 **End-to-end tests with Selenium + Socket.IO**  
- 📈 **Overlay performance simulations and analysis**  

---

## 🛠️ Getting Started

### 1. Set up the environment

```
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Run locally

```
flask run
```

Visit [http://localhost:5000](http://localhost:5000) to draw with yourself.

---

## 🧪 Running Tests

Unit, integration, and Selenium browser tests are all runnable via:

```
python3 -m unittest test.py
```

Tests include:

- Unit tests for the k-gossip overlay (`compute_k`)
- Socket.IO-based integration tests (fullmesh and gossip)
- Automated canvas painting test via Selenium

---

## 🌐 Deployment

This app is production-ready for platforms like Render:

```
gunicorn --worker-class eventlet --workers 1 --bind 0.0.0.0:$PORT app:application
```

Make sure your `.env` file contains:

```
SECRET_KEY=...
TURN_SECRET=...      # hex-encoded key
TURN_URLS=stun:...,turn:...
MODE=kgossip          # or fullmesh
NINES=3               # reliability parameter for k-gossip
```

---

## 📡 TURN Server Setup

For NAT traversal and connectivity behind firewalls:

1. Deploy a `coturn` server on DigitalOcean or any VPS.  
2. Set up shared secret authentication (`static-auth-secret`).  
3. Configure the following environment variables:

```
TURN_SECRET=your_hex_secret
TURN_URLS=turn:your.turn.domain:3478
```

---

## 📁 Project Structure

```
.
├── app.py                 # Flask backend + signaling server
├── test.py               # Tests (unit + integration + selenium)
├── requirements.txt      # Dependencies
├── templates/
│   └── index.html        # Main canvas app
├── graphs/
│   ├── k.py              # Plots k vs N for various nines
│   └── simulation.py     # Simulates gossip overlay performance
└── static/               # (optional future expansion)
```

---

## 📊 Graphs & Simulations

Run `graphs/simulation.py` to visualize:

- Rounds vs Network Size  
- Messages vs Network Size  
- Propagation Latency  
- CPU and bandwidth distribution per peer  

This helps compare fullmesh vs k-gossip overlays at scale.

---

## 📜 License

MIT License. Feel free to fork, modify, and build on it.
