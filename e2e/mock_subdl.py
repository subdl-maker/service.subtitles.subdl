"""A stand-in for api.subdl.com and dl.subdl.com, served over HTTPS inside the test container.

/etc/hosts points both names at 127.0.0.1 and a test CA signs the certificate, so the
add-on's real client, TLS checks and redirect rules all run unchanged. Every request is
appended to /harness/out/requests.jsonl for the driver to assert on.
"""

import io
import json
import ssl
import sys
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qsl, urlsplit

KEY = "TestKey-not-real-0123456789"
MATRIX = "The.Matrix.1999.1080p.BluRay.x264-GROUP"
LOG = "/harness/out/requests.jsonl"
SRT_FA = "1\n00:00:01,000 --> 00:00:04,000\nسلام نئو\n\n".encode("utf-8")
SRT_EN = b"1\n00:00:01,000 --> 00:00:04,000\nHello, Neo.\n\n"
SRT_EP = b"1\n00:00:01,000 --> 00:00:04,000\nEpisode five.\n\n"


def row(sub_id, language, release, **extra):
    data = {
        "release_name": release, "name": "SUBDL::subtitle-%d.zip" % sub_id, "lang": language.lower(),
        "author": "tester", "url": "/subtitle/%d-%d.zip?api_key=%s" % (sub_id, sub_id + 1000, KEY),
        "subtitlePage": "/s/info/x%d" % sub_id, "season": 0, "episode": None, "language": language,
        "framerate": 0, "fps": None, "hi": False, "releases": [], "episode_from": None,
        "episode_end": 0, "full_season": False,
    }
    data.update(extra)
    return data


def zipped(files):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return buffer.getvalue()


MATRIX_RESULT = {"status": True, "totalPages": 1, "currentPage": 1,
                 "results": [{"sd_id": 1, "type": "movie", "name": "The Matrix", "imdb_id": "tt0133093",
                              "tmdb_id": 603, "year": 1999}],
                 "subtitles": [row(1, "EN", "The.Matrix.1999.720p.WEB-DL-OTHER"),
                               row(2, "FA", "The.Matrix.1999.720p.WEB-DL-OTHER"),
                               row(3, "FA", MATRIX, hi=True),
                               row(4, "ZH_BG", MATRIX)]}
SHOW_RESULT = {"status": True, "totalPages": 1, "currentPage": 1,
               "results": [{"sd_id": 2, "type": "tv", "name": "Breaking Bad", "imdb_id": "tt0903747",
                            "tmdb_id": 1396, "year": 2008}],
               "subtitles": [row(5, "EN", "Breaking.Bad.S01.BluRay.x264-DEMAND", season=1, full_season=True,
                                 unpack_files=[
                                     {"file_n_id": "e4", "name": "Breaking.Bad.S01E04.720p.BluRay.x264-DEMAND.srt",
                                      "release_name": "", "season": 1, "episode": 4, "language": "EN",
                                      "hi": False, "format": "srt", "size": 100, "md5": "0" * 32,
                                      "url": "/subtitle/packnid/e4?api_key=" + KEY},
                                     {"file_n_id": "e5", "name": "Breaking.Bad.S01E05.720p.BluRay.x264-DEMAND.srt",
                                      "release_name": "", "season": 1, "episode": 5, "language": "EN",
                                      "hi": False, "format": "srt", "size": 100, "md5": "0" * 32,
                                      "url": "/subtitle/packnid/e5?api_key=" + KEY}])]}
ACCOUNT = {"status": True, "user": {"id": 7, "name": "Test Viewer", "username": "testviewer"},
           "apiAccount": {"requests": {"today": 12, "limit": 2000}, "downloads": {"today": 3, "limit": 0}},
           "pro": {"isPaid": False, "plan": None}}
FILES = {
    "/subtitle/3-1003.zip": zipped({MATRIX + ".srt": SRT_FA, "Visit SubDL.url": b"[InternetShortcut]"}),
    "/subtitle/1-1001.zip": zipped({"english.srt": SRT_EN}),
    "/subtitle/packnid/e5": SRT_EP,
}


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass

    def do_GET(self):
        split = urlsplit(self.path)
        query = dict(parse_qsl(split.query))
        with open(LOG, "a") as log:
            log.write(json.dumps({"host": self.headers.get("Host"), "path": split.path, "query": query,
                                  "ua": self.headers.get("User-Agent")}) + "\n")
        host = (self.headers.get("Host") or "").split(":")[0]
        if host == "api.subdl.com" and split.path == "/api/v1/subtitles":
            if query.get("api_key") != KEY:
                return self.json(403, {"status": False, "statusCode": 403, "error": "not_authorized",
                                       "message": "Not Authorized"})
            if query.get("film_name") == "limit test":
                return self.json(429, {"status": False, "statusCode": 429, "error": "daily_limit",
                                       "message": "Daily Limit"})
            if query.get("imdb_id") == "tt0133093" or query.get("file_name", "").startswith("The.Matrix"):
                return self.json(200, MATRIX_RESULT)
            if query.get("file_name", "").startswith("Breaking.Bad") or query.get("film_name") == "Breaking Bad":
                return self.json(200, SHOW_RESULT)
            return self.json(200, {"status": False, "error": "can't find movie or tv"})
        if host == "api.subdl.com" and split.path == "/api/v1/me":
            if query.get("api_key") != KEY:
                return self.json(403, {"status": False, "error": "not_authorized"})
            return self.json(200, ACCOUNT)
        if host == "dl.subdl.com" and split.path in FILES:
            if query.get("api_key") != KEY:
                return self.json(403, {"status": False, "error": "expected the key"})
            body = FILES[split.path]
            self.send_response(200)
            name = split.path.rsplit("/", 1)[-1]
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Disposition", "attachment; filename=\"%s%s\"" % (
                name, "" if name.endswith(".zip") else ".srt"))
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.json(404, {"status": False, "error": "subtitle_not_found"})

    def json(self, status, body):
        data = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def main():
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(sys.argv[1], sys.argv[2])
    server = ThreadingHTTPServer(("127.0.0.1", 443), Handler)
    server.socket = context.wrap_socket(server.socket, server_side=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
