"""Shared test helpers: import paths, a fake HTTP transport and SubDL-shaped data.

The search rows mirror what api/src/app/api/subtitleResponse.ts (mapPublicApiSubtitle)
returns from GET /api/v1/subtitles, including the api_key the API appends to every
download address.
"""

import io
import json
import os
import sys
import zipfile
from email.message import Message
from urllib.parse import parse_qsl, urlsplit

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADDON_DIR = os.path.join(ROOT, "service.subtitles.subdl")
for path in (os.path.join(ROOT, "tests", "kodi_fakes"), os.path.join(ADDON_DIR, "resources", "lib")):
    if path not in sys.path:
        sys.path.insert(0, path)

from subdl import api  # noqa: E402

KEY = "TestKey-not-real-0123456789"


def make_headers(values=None):
    message = Message()
    for name, value in (values or {}).items():
        message[name] = value
    return message


def response(status=200, body=None, headers=None):
    if isinstance(body, (dict, list)):
        body = json.dumps(body).encode("utf-8")
    return api.Response(status, make_headers(headers), body or b"")


class FakeTransport:
    """Answers requests from a queue and remembers what was asked."""

    def __init__(self, *answers):
        self.answers = list(answers)
        self.requests = []

    def __call__(self, request, timeout, limit):
        self.requests.append(request)
        if not self.answers:
            raise AssertionError("unexpected request to %s" % urlsplit(request.full_url).path)
        answer = self.answers.pop(0)
        if isinstance(answer, BaseException):
            raise answer
        return answer

    def query(self, index=-1):
        return dict(parse_qsl(urlsplit(self.requests[index].full_url).query))

    def path(self, index=-1):
        return urlsplit(self.requests[index].full_url).path


def subtitle(sub_id=3197651, **fields):
    row = {
        "release_name": "The.Matrix.1999.1080p.BluRay.x264-GROUP",
        "name": "SUBDL::subtitle-%d.zip" % sub_id,
        "lang": "english",
        "author": "someone",
        "url": "/subtitle/%d-%d.zip?api_key=%s" % (sub_id, sub_id + 1000, KEY),
        "subtitlePage": "/s/info/abc%d" % sub_id,
        "season": 0,
        "episode": None,
        "language": "EN",
        "framerate": 0,
        "fps": None,
        "hi": False,
        "releases": [],
        "episode_from": None,
        "episode_end": 0,
        "full_season": False,
    }
    row.update(fields)
    return row


def pack_file(file_id, name, season, episode, fmt="srt"):
    return {
        "file_n_id": file_id,
        "name": name,
        "release_name": "",
        "season": season,
        "episode": episode,
        "language": "EN",
        "hi": False,
        "format": fmt,
        "size": 40000,
        "md5": "0" * 32,
        "url": "/subtitle/packnid/%s?api_key=%s" % (file_id, KEY),
    }


def search_body(rows, title=None, pages=1):
    title = title or {"sd_id": 1, "type": "movie", "name": "The Matrix", "imdb_id": "tt0133093",
                      "tmdb_id": 603, "year": 1999}
    return {"status": True, "results": [title], "subtitles": rows, "totalPages": pages, "currentPage": 1}


TITLE_MISS = {"status": False, "error": "can't find movie or tv"}


def zip_bytes(files):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in files.items():
            archive.writestr(name, data)
    return buffer.getvalue()


SRT = b"1\r\n00:00:01,000 --> 00:00:02,000\r\nHello.\r\n"
