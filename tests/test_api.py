import unittest
import urllib.error
from email.utils import format_datetime
from datetime import datetime, timezone

from tests.support import KEY, TITLE_MISS, FakeTransport, response, search_body, subtitle

from subdl import api
from subdl.api import SubDLError

UA = "SubDL-Kodi/1.0.0 (service.subtitles.subdl; Kodi/21.2; Linux)"
NOW = 1_800_000_000.0


def make_client(*answers, key=KEY):
    transport = FakeTransport(*answers)
    sleeps = []
    client = api.SubDLClient(key, UA, transport=transport, sleep=sleeps.append, clock=lambda: NOW)
    return client, transport, sleeps


class SearchRequestTest(unittest.TestCase):
    def test_sends_key_client_and_params_to_v1_search(self):
        client, transport, _ = make_client(response(200, search_body([subtitle()])))
        body = client.search({"imdb_id": "tt0133093", "type": "movie", "languages": "EN,FA", "empty": ""})

        self.assertTrue(body["status"])
        request = transport.requests[0]
        self.assertTrue(request.full_url.startswith("https://api.subdl.com/api/v1/subtitles?"))
        self.assertEqual(transport.query(), {
            "imdb_id": "tt0133093", "type": "movie", "languages": "EN,FA", "api_key": KEY, "client": "kodi",
        })
        self.assertEqual(request.get_header("User-agent"), UA)
        self.assertEqual(request.get_header("Accept"), "application/json")
        self.assertEqual(request.get_header("Accept-encoding"), "gzip")

    def test_missing_key_sends_nothing(self):
        client, transport, _ = make_client(key="  ")
        with self.assertRaises(SubDLError) as caught:
            client.search({"film_name": "x"})
        self.assertEqual(caught.exception.kind, SubDLError.MISSING_KEY)
        self.assertEqual(transport.requests, [])

    def test_title_miss_is_an_answer_not_an_error(self):
        client, _, _ = make_client(response(200, TITLE_MISS))
        body = client.search({"film_name": "No Such Film"})
        self.assertTrue(api.is_title_miss(body))

    def test_other_failed_answers_raise(self):
        client, _, _ = make_client(response(200, {"status": False, "error": "Public API is disabled"}))
        with self.assertRaises(SubDLError) as caught:
            client.search({"film_name": "x"})
        self.assertEqual(caught.exception.kind, SubDLError.FAILED)


class SearchErrorTest(unittest.TestCase):
    def assert_kind(self, answer, kind):
        client, transport, sleeps = make_client(answer)
        with self.assertRaises(SubDLError) as caught:
            client.search({"film_name": "x"})
        self.assertEqual(caught.exception.kind, kind)
        self.assertNotIn(KEY, str(caught.exception))
        return caught.exception, transport, sleeps

    def test_refused_key(self):
        body = {"status": False, "statusCode": 403, "error": "not_authorized", "message": "Not Authorized"}
        self.assert_kind(response(403, body), SubDLError.INVALID_KEY)

    def test_daily_limit_is_not_retried(self):
        body = {"status": False, "statusCode": 429, "error": "daily_limit", "message": "Daily Limit"}
        _, transport, sleeps = self.assert_kind(response(429, body), SubDLError.DAILY_LIMIT)
        self.assertEqual(len(transport.requests), 1)
        self.assertEqual(sleeps, [])

    def test_bad_request(self):
        self.assert_kind(response(400, {"success": False, "error": "Language error"}), SubDLError.FAILED)

    def test_server_error(self):
        self.assert_kind(response(500, b"<html>"), SubDLError.FAILED)


class RetryTest(unittest.TestCase):
    def test_per_minute_limit_waits_retry_after_then_succeeds(self):
        busy = response(429, {"status": False, "error": "rate_limit", "retryAfterSeconds": 3},
                        {"Retry-After": "3"})
        client, transport, sleeps = make_client(busy, response(200, search_body([])))
        self.assertTrue(client.search({"film_name": "x"})["status"])
        self.assertEqual(sleeps, [3.0])
        self.assertEqual(len(transport.requests), 2)

    def test_retry_after_as_http_date(self):
        when = format_datetime(datetime.fromtimestamp(NOW + 4, tz=timezone.utc), usegmt=True)
        busy = response(429, {"status": False, "error": "service_busy"}, {"Retry-After": when})
        client, _, sleeps = make_client(busy, response(200, search_body([])))
        client.search({"film_name": "x"})
        self.assertEqual(sleeps, [4.0])

    def test_retry_after_from_body_when_header_missing(self):
        busy = response(429, {"status": False, "error": "service_busy", "retryAfterSeconds": 5})
        client, _, sleeps = make_client(busy, response(200, search_body([])))
        client.search({"film_name": "x"})
        self.assertEqual(sleeps, [5.0])

    def test_long_retry_after_gives_up_at_once(self):
        busy = response(429, {"status": False, "error": "rate_limit"}, {"Retry-After": "60"})
        client, transport, sleeps = make_client(busy)
        with self.assertRaises(SubDLError) as caught:
            client.search({"film_name": "x"})
        self.assertEqual(caught.exception.kind, SubDLError.BUSY)
        self.assertEqual(caught.exception.retry_after, 60.0)
        self.assertEqual((len(transport.requests), sleeps), (1, []))

    def test_gateway_errors_are_retried_twice(self):
        client, transport, sleeps = make_client(response(503), response(502), response(200, search_body([])))
        self.assertTrue(client.search({"film_name": "x"})["status"])
        self.assertEqual(sleeps, [2.0, 2.0])

    def test_gateway_errors_that_persist_are_busy(self):
        client, transport, _ = make_client(response(503), response(503), response(503))
        with self.assertRaises(SubDLError) as caught:
            client.search({"film_name": "x"})
        self.assertEqual(caught.exception.kind, SubDLError.BUSY)
        self.assertEqual(len(transport.requests), 3)

    def test_network_error_is_retried_once(self):
        client, _, sleeps = make_client(urllib.error.URLError("down"), response(200, search_body([])))
        self.assertTrue(client.search({"film_name": "x"})["status"])
        self.assertEqual(sleeps, [1.0])

    def test_network_error_twice(self):
        client, transport, _ = make_client(TimeoutError("slow"), ConnectionResetError("reset"))
        with self.assertRaises(SubDLError) as caught:
            client.search({"film_name": "x"})
        self.assertEqual(caught.exception.kind, SubDLError.NETWORK)
        self.assertEqual(caught.exception.detail, "ConnectionResetError")
        self.assertEqual(len(transport.requests), 2)


class AccountTest(unittest.TestCase):
    def test_account_reads_me_with_the_key(self):
        client, transport, _ = make_client(response(200, {"status": True, "user": {"username": "viewer"}}))
        self.assertEqual(client.account()["user"]["username"], "viewer")
        self.assertEqual(transport.path(), "/api/v1/me")
        self.assertEqual(transport.query(), {"api_key": KEY})

    def test_account_with_refused_key(self):
        client, _, _ = make_client(response(403, {"status": False, "error": "not_authorized"}))
        with self.assertRaises(SubDLError) as caught:
            client.account()
        self.assertEqual(caught.exception.kind, SubDLError.INVALID_KEY)


class DownloadTest(unittest.TestCase):
    def test_download_puts_the_viewers_key_back_on_a_stripped_path(self):
        answer = response(200, b"PK\x03\x04data", {
            "Content-Disposition": "attachment; filename*=UTF-8''The%20Matrix%20%C3%A9.zip"})
        client, transport, _ = make_client(answer)
        data, name = client.download("/subtitle/3197651-3198651.zip")
        self.assertEqual(data, b"PK\x03\x04data")
        self.assertEqual(name, "The Matrix é.zip")
        self.assertEqual(transport.requests[0].full_url,
                         "https://dl.subdl.com/subtitle/3197651-3198651.zip?api_key=" + KEY)
        self.assertEqual(transport.requests[0].get_header("Accept"), "*/*")

    def test_download_keeps_other_parameters(self):
        client, transport, _ = make_client(response(200, b"1\n00:00:01,000 --> 00:00:02,000\nx\n"))
        client.download("/mobile/nid123?hash=abc&api_key=someone-elses")
        self.assertEqual(transport.path(), "/mobile/nid123")
        self.assertEqual(transport.query(), {"hash": "abc", "api_key": KEY})

    def test_download_refuses_addresses_off_subdl(self):
        client, transport, _ = make_client()
        for path in ("https://evil.example/subtitle/1-2.zip", "http://dl.subdl.com/subtitle/1-2.zip",
                     "/api/v1/me", "https://subdl.com.evil.example/subtitle/1-2.zip"):
            with self.assertRaises(SubDLError, msg=path):
                client.download(path)
        self.assertEqual(transport.requests, [])

    def test_daily_download_limit(self):
        body = {"error": "api_download_limit_exceeded",
                "message": "Free daily download limit reached (50/day).", "retryAfterSeconds": 3600}
        client, transport, sleeps = make_client(response(429, body, {"Retry-After": "3600"}))
        with self.assertRaises(SubDLError) as caught:
            client.download("/subtitle/1-2.zip")
        self.assertEqual(caught.exception.kind, SubDLError.DOWNLOAD_LIMIT)
        self.assertEqual((len(transport.requests), sleeps), (1, []))

    def test_anonymous_download_limit(self):
        client, _, _ = make_client(response(429, {"error": "download_limit_exceeded"}))
        with self.assertRaises(SubDLError) as caught:
            client.download("/subtitle/1-2.zip")
        self.assertEqual(caught.exception.kind, SubDLError.DOWNLOAD_LIMIT)

    def test_removed_subtitle(self):
        body = {"status": False, "error": "subtitle_not_found", "message": "Subtitle not found"}
        client, _, _ = make_client(response(404, body))
        with self.assertRaises(SubDLError) as caught:
            client.download("/subtitle/1-2.zip")
        self.assertEqual(caught.exception.kind, SubDLError.NOT_FOUND)

    def test_empty_body_is_a_failure(self):
        client, _, _ = make_client(response(200, b""))
        with self.assertRaises(SubDLError):
            client.download("/subtitle/1-2.zip")


class HelperTest(unittest.TestCase):
    def test_is_subdl_url(self):
        self.assertTrue(api.is_subdl_url("https://dl.subdl.com/subtitle/1-2.zip"))
        self.assertTrue(api.is_subdl_url("https://subdl.com/panel/api"))
        self.assertTrue(api.is_subdl_url("https://api.subdl.com:443/api/v1/me"))
        for url in ("http://dl.subdl.com/x", "https://evilsubdl.com/x", "https://subdl.com.evil.example/x",
                    "https://dl.subdl.com:8443/x", "ftp://dl.subdl.com/x", "https://[bad/x", ""):
            self.assertFalse(api.is_subdl_url(url), url)

    def test_strip_api_key(self):
        self.assertEqual(api.strip_api_key("/subtitle/1-2.zip?api_key=" + KEY), "/subtitle/1-2.zip")
        self.assertEqual(api.strip_api_key("/mobile/n?hash=abc&API_KEY=x"), "/mobile/n?hash=abc")
        self.assertEqual(api.strip_api_key("/subtitle/1-2.zip"), "/subtitle/1-2.zip")

    def test_is_download_path(self):
        self.assertTrue(api.is_download_path("/subtitle/1-2.zip?api_key=x"))
        self.assertTrue(api.is_download_path("/subtitle/nid/fileid"))
        self.assertTrue(api.is_download_path("/mobile/nid?hash=abc"))
        self.assertFalse(api.is_download_path("/s/info/abc"))
        self.assertFalse(api.is_download_path("//evil.example/subtitle/1"))

    def test_parse_retry_after(self):
        self.assertEqual(api.parse_retry_after("120", NOW), 120.0)
        self.assertEqual(api.parse_retry_after(" 1.5 ", NOW), 1.5)
        self.assertIsNone(api.parse_retry_after("", NOW))
        self.assertIsNone(api.parse_retry_after("soon", NOW))
        past = format_datetime(datetime.fromtimestamp(NOW - 30, tz=timezone.utc), usegmt=True)
        self.assertEqual(api.parse_retry_after(past, NOW), 0.0)
        future = format_datetime(datetime.fromtimestamp(NOW + 90, tz=timezone.utc), usegmt=True)
        self.assertEqual(api.parse_retry_after(future, NOW), 90.0)

    def test_filename_from_disposition(self):
        self.assertEqual(api.filename_from_disposition('attachment; filename="a b.srt"'), "a b.srt")
        self.assertEqual(api.filename_from_disposition("attachment; filename=plain.srt"), "plain.srt")
        self.assertEqual(api.filename_from_disposition("attachment; filename*=UTF-8''%D9%81.srt"), "ف.srt")
        self.assertEqual(api.filename_from_disposition("attachment; filename*=bogus''x.srt"), "x.srt")
        self.assertEqual(api.filename_from_disposition(""), "")


if __name__ == "__main__":
    unittest.main()
