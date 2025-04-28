import unittest
import threading
import time

from app import app, socketio, compute_k, redis_client, PEER_SET

# When Redis is not configured, we maintain a local in‑memory set of peers for
# development & unit‑tests. Import it if present.
try:
    from app import LOCAL_PEERS  # noqa: WPS433
except ImportError:  # pragma: no cover – Redis always available in CI
    LOCAL_PEERS = None  # type: ignore

# --- Unit Tests -------------------------------------------------------------
class ComputeKUnitTests(unittest.TestCase):
    def test_small_n_peers(self):
        self.assertEqual(compute_k(1, 5), 1)
        self.assertEqual(compute_k(0, 5), 0)

    def test_none_nines(self):
        self.assertEqual(compute_k(5, None), 5)

    def test_normal_case(self):
        # ln(10) + 2*ln(10) = 6.9078 → ceil = 7, clamped ≤10 ⇒ 7
        self.assertEqual(compute_k(10, 2), 7)

    def test_clamped(self):
        self.assertEqual(compute_k(3, 1000), 3)


# --- Integration Tests for Socket.IO ---------------------------------------
class IntegrationTests(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['MODE'] = 'fullmesh'

        # Wipe any residual peers between tests
        if redis_client:
            redis_client.delete(PEER_SET)
        elif LOCAL_PEERS is not None:
            LOCAL_PEERS.clear()

        self.client1 = socketio.test_client(app)
        self.client2 = socketio.test_client(app)

    def tearDown(self):
        for client in (self.client1, self.client2):
            try:
                client.disconnect()
            except RuntimeError:
                pass

    def test_fullmesh_join_signal_disconnect(self):
        self.client1.emit('join', {'peerId': 'A'})
        msgs1 = self.client1.get_received()
        self.assertTrue(any(m['name'] == 'peers' and m['args'][0]['peers'] == [] for m in msgs1))

        self.client2.emit('join', {'peerId': 'B'})
        msgs2 = self.client2.get_received()

        expected_peers_for_B = ['A'] if redis_client or (LOCAL_PEERS and len(LOCAL_PEERS)) else []
        self.assertTrue(any(m['name'] == 'peers' and m['args'][0]['peers'] == expected_peers_for_B for m in msgs2))

        msgs1 = self.client1.get_received()
        self.assertTrue(any(m['name'] == 'peer-joined' and m['args'][0]['peerId'] == 'B' for m in msgs1))

        signal_msg = {'to': 'A', 'from': 'B', 'signal': {'foo': 'bar'}}
        self.client2.emit('signal', signal_msg)
        recv_signal = self.client1.get_received()
        self.assertTrue(any(m['name'] == 'signal' and m['args'][0] == signal_msg for m in recv_signal))

        # disconnect B explicitly; tearDown handles the rest
        self.client2.disconnect()

    def test_kgossip_join(self):
        app.config['MODE'] = 'kgossip'
        app.config['NINES'] = 1
        if redis_client:
            redis_client.delete(PEER_SET)
        elif LOCAL_PEERS is not None:
            LOCAL_PEERS.clear()

        c1 = socketio.test_client(app)
        c1.emit('join', {'peerId': 'A'})
        self.assertTrue(any(m['name'] == 'peers' and m['args'][0]['peers'] == [] for m in c1.get_received()))

        c2 = socketio.test_client(app)
        c2.emit('join', {'peerId': 'B'})
        sample_msg = next(m for m in c2.get_received() if m['name'] == 'peers')
        sample_list = sample_msg['args'][0]['peers']

        if redis_client or (LOCAL_PEERS and len(LOCAL_PEERS)):
            # with state available, B should learn about A
            self.assertEqual(sample_list, ['A'])
        else:
            # stateless fallback ⇒ no peers
            self.assertEqual(sample_list, [])

        # client A should get peer‑joined for B regardless
        msgsA = c1.get_received()
        self.assertTrue(any(m['name'] == 'peer-joined' and m['args'][0]['peerId'] == 'B' for m in msgsA))

        c1.disconnect()
        c2.disconnect()


# --- Selenium Canvas Tests --------------------------------------------------
class CanvasPaintingTests(unittest.TestCase):
    """These UI tests assume Chrome + a local display. They are optional."""

    @classmethod
    def setUpClass(cls):
        app.config['TESTING'] = True

        # spin up the server in a background thread
        cls.server_thread = threading.Thread(
            target=lambda: socketio.run(app, host='127.0.0.1', port=5000)
        )
        cls.server_thread.daemon = True
        cls.server_thread.start()
        time.sleep(2)  # give server a moment

        try:
            from selenium import webdriver  # noqa: WPS433 – only in test env
            from selenium.webdriver.chrome.options import Options

            chrome_opts = Options()
            chrome_opts.add_argument('--headless=new')
            cls.driver = webdriver.Chrome(options=chrome_opts)
            cls.driver.get('http://127.0.0.1:5000')
        except Exception as exc:  # pragma: no cover – Selenium not available
            cls.driver = None
            print('⚠️  Selenium tests skipped:', exc)

    @classmethod
    def tearDownClass(cls):
        if cls.driver:
            cls.driver.quit()

    def test_canvas_painting(self):
        if not getattr(self, 'driver', None):
            self.skipTest('Selenium not configured')

        # click cell (2,2)
        self.driver.execute_script("""
            const cvs = document.getElementById('canvas');
            const rect = cvs.getBoundingClientRect();
            const SCALE = 8;
            const clickX = rect.left + 2 * SCALE + SCALE / 2;
            const clickY = rect.top + 2 * SCALE + SCALE / 2;
            cvs.dispatchEvent(new MouseEvent('click', {clientX: clickX, clientY: clickY, bubbles: true}));
        """)

        color = self.driver.execute_script("""
            const cvs = document.getElementById('canvas');
            const ctx = cvs.getContext('2d');
            const SCALE = 8;
            const sampleX = 2 * SCALE + Math.floor(SCALE / 2);
            const sampleY = 2 * SCALE + Math.floor(SCALE / 2);
            const d = ctx.getImageData(sampleX, sampleY, 1, 1).data;
            return `rgba(${d[0]},${d[1]},${d[2]},${d[3]})`;
        """)
        self.assertEqual(color, 'rgba(0,0,0,255)')


if __name__ == '__main__':
    unittest.main()
