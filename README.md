# P2Place
Peer-to-peer implementation of r/place concept

## Usage

1. Run `python -m venv venv` and `source venv/bin/activate`.
2. Install dependencies with `pip install -r requirements.txt`.
3. Run website with `flask run`. The site will be live at `http://localhost:5000`.

## Tests

Run tests with `python3 -m unittest test.py`

## Production

Run server on Render with `gunicorn --worker-class eventlet --workers 1 --bind 0.0.0.0:$PORT app:application`

## TURN

Run a coturn server in a droplet on Digital Ocean and provide UDP and TCP connection options in the env variables