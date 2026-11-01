"""The real urllib transport, against a local HTTP server (no internet needed)."""

import gzip
import http.server
import threading
import unittest
import urllib.request

from tests import support  # noqa: F401 - sets up import paths

from subdl import api
from subdl.api import SubDLError


class Handler(http.server.BaseHTTPRequestHandler):
    seen = []

    def log_message(self, *args):
        pass

    def do_GET(self):
        Handler.seen.append(self.path)
        if self.path == "/json":
            self.reply(200, b'{"status": true}', {"Content-Type": "application/json"})
        elif self.path == "/gzip":
            self.reply(200, gzip.compress(b'{"status": true, "zipped": 1}'), {"Content-Encoding": "gzip"})
        elif self.path == "/big":
            self.reply(200, b"x" * 5000)
        elif self.path == "/gzip-bomb":
            self.reply(200, gzip.compress(b"0" * 100000), {"Content-Encoding": "gzip"})
        elif self.path == "/limit":
            self.reply(429, b'{"error": "daily_limit"}', {"Retry-After": "30"})
        elif self.path == "/redirect-away":
            self.reply(302, b"", {"Location": "http://127.0.0.1:%d/landed" % self.server.server_port})
        else:
            self.reply(404, b'{"error": "nope"}')

    def reply(self, status, body, headers=None):
        self.send_response(status)
        for name, value in (headers or {}).items():
            self.send_header(name, value)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class TransportTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = "http://127.0.0.1:%d" % cls.server.server_port

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        Handler.seen = []

    def get(self, path, limit=4096):
        return api.urllib_transport(urllib.request.Request(self.base + path), 5, limit)

    def test_plain_json(self):
        answer = self.get("/json")
        self.assertEqual((answer.status, answer.json()), (200, {"status": True}))

    def test_gzip_is_decoded(self):
        self.assertEqual(self.get("/gzip").json(), {"status": True, "zipped": 1})

    def test_error_status_is_an_answer_with_its_body(self):
        answer = self.get("/limit")
        self.assertEqual(answer.status, 429)
        self.assertEqual(answer.json(), {"error": "daily_limit"})
        self.assertEqual(answer.header("Retry-After"), "30")

    def test_size_cap(self):
        with self.assertRaises(SubDLError):
            self.get("/big", limit=1000)

    def test_gzip_cap_applies_after_decoding(self):
        with self.assertRaises(SubDLError):
            self.get("/gzip-bomb", limit=4096)

    def test_redirect_off_subdl_is_refused_before_it_is_followed(self):
        with self.assertRaises(SubDLError):
            self.get("/redirect-away")
        self.assertEqual(Handler.seen, ["/redirect-away"])


class RedirectHandlerTest(unittest.TestCase):
    class FakeBody:
        closed = False

        def close(self):
            self.closed = True

    def test_redirects_within_subdl_are_followed(self):
        handler = api._SubDLRedirectsOnly()
        request = urllib.request.Request("https://dl.subdl.com/subtitle/1-2.zip")
        follow = handler.redirect_request(request, self.FakeBody(), 302, "Found", {},
                                          "https://dl.subdl.com/subtitle/1-2.zip?x=1")
        self.assertEqual(follow.full_url, "https://dl.subdl.com/subtitle/1-2.zip?x=1")

    def test_redirects_elsewhere_close_the_response(self):
        body = self.FakeBody()
        with self.assertRaises(SubDLError):
            api._SubDLRedirectsOnly().redirect_request(
                urllib.request.Request("https://dl.subdl.com/subtitle/1-2.zip"), body, 302, "Found", {},
                "https://cdn.example/1-2.zip")
        self.assertTrue(body.closed)


if __name__ == "__main__":
    unittest.main()
