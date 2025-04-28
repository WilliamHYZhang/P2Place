import unittest
import threading
import time

from app import app, socketio, compute_k, peers

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# --- Unit Tests ---
class ComputeKUnitTests(unittest.TestCase):
    def test_compute_k_small_n_peers(self):
        self.assertEqual(compute_k(1, 5), 1)
        self.assertEqual(compute_k(0, 5), 0)

    def test_compute_k_none_nines(self):
        self.assertEqual(compute_k(5, None), 3)

    def test_compute_k_normal_case(self):
        self.assertEqual(compute_k(10, 2), 2)

    def test_compute_k_clamped(self):
        self.assertEqual(compute_k(3, 1000), 3)


# --- Integration Tests for SocketIO ---
class IntegrationTests(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['MODE'] = 'fullmesh'
        peers.clear()
        self.client1 = socketio.test_client(app)
        self.client2 = socketio.test_client(app)

    def tearDown(self):
        for client in (self.client1, self.client2):
            try:
                client.disconnect()
            except RuntimeError:
                pass

    def test_fullmesh_join_and_signal_and_disconnect(self):
        self.client1.emit('join', {'peerId': 'A'})
        msgs1 = self.client1.get_received()
        self.assertTrue(any(m['name']=='peers' and m['args'][0]['peers']==[] for m in msgs1))

        self.client2.emit('join', {'peerId': 'B'})
        msgs2 = self.client2.get_received()
        self.assertTrue(any(m['name']=='peers' and 'A' in m['args'][0]['peers'] for m in msgs2))
        msgs1 = self.client1.get_received()
        self.assertTrue(any(m['name']=='peer-joined' and m['args'][0]['peerId']=='B' for m in msgs1))

        signal_msg = {'to':'A', 'from':'B', 'signal':{'foo':'bar'}}
        self.client2.emit('signal', signal_msg)
        recv_signal = self.client1.get_received()
        self.assertTrue(any(m['name']=='signal' and m['args'][0]==signal_msg for m in recv_signal))

        # Only disconnect once; tearDown handles the rest
        self.client2.disconnect()

    def test_kgossip_join(self):
        app.config['MODE'] = 'kgossip'
        app.config['NINES'] = 1
        peers.clear()

        c1 = socketio.test_client(app)
        c1.emit('join', {'peerId':'A'})
        msgs1 = c1.get_received()
        self.assertTrue(any(m['name']=='peers' and m['args'][0]['peers']==[] for m in msgs1))

        c2 = socketio.test_client(app)
        c2.emit('join', {'peerId':'B'})
        msgs2 = c2.get_received()
        self.assertTrue(any(m['name']=='peers' and m['args'][0]['peers']==['A'] for m in msgs2))
        msgsA = c1.get_received()
        self.assertTrue(any(m['name']=='peer-joined' and m['args'][0]['peerId']=='B' for m in msgsA))

        c1.disconnect()
        c2.disconnect()


# --- Integration Tests for Canvas Painting via Selenium ---
class CanvasPaintingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config['TESTING'] = True
        # start server in background
        cls.server_thread = threading.Thread(
            target=lambda: socketio.run(app, host='127.0.0.1', port=5000)
        )
        cls.server_thread.daemon = True
        cls.server_thread.start()
        time.sleep(3)  # give server time to bind

        options = webdriver.ChromeOptions()
        # options.add_argument('--headless')
        options.add_argument('--remote-debugging-port=9222')
        cls.driver = webdriver.Chrome(options=options)
        cls.driver.get('http://127.0.0.1:5000')

    @classmethod
    def tearDownClass(cls):
        cls.driver.quit()


    def test_canvas_painting(self):
        # click at cell (2,2)
        self.driver.execute_script("""
        const cvs = document.getElementById('canvas');
        const rect = cvs.getBoundingClientRect();
        const SCALE = 8;
        // click in the center of the grid cell
        const clickX = rect.left + 2 * SCALE + SCALE/2;
        const clickY = rect.top + 2 * SCALE + SCALE/2;
        cvs.dispatchEvent(new MouseEvent('click', {clientX: clickX, clientY: clickY, bubbles: true}));
        """
        )
        # sample the pixel at the center of cell (2,2)
        color = self.driver.execute_script("""
        const cvs = document.getElementById('canvas');
        const ctx = cvs.getContext('2d');
        const SCALE = 8;
        const sampleX = 2 * SCALE + Math.floor(SCALE/2);
        const sampleY = 2 * SCALE + Math.floor(SCALE/2);
        const d = ctx.getImageData(sampleX, sampleY, 1, 1).data;
        return `rgba(${d[0]},${d[1]},${d[2]},${d[3]})`;
        """
        )
        self.assertEqual(color, 'rgba(0,0,0,255)', 'Canvas pixel should be painted black')

if __name__ == '__main__':
    unittest.main()
