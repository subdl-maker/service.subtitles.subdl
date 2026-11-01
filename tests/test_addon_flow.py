"""The add-on as Kodi runs it: service.py's run() with fake Kodi modules and HTTP."""

import os
import runpy
import shutil
import sys
import tempfile
import time
import unittest
from unittest import mock
from urllib.parse import parse_qsl, urlsplit

from tests.support import (ADDON_DIR, KEY, SRT, TITLE_MISS, FakeTransport, pack_file, response, search_body,
                           subtitle, zip_bytes)

from kodistate import state
from subdl import addon, api

PANEL = "https://subdl.com/panel/api"
MATRIX = "The.Matrix.1999.1080p.BluRay.x264-GROUP"


class FlowTest(unittest.TestCase):
    def setUp(self):
        self.profile = tempfile.mkdtemp()
        state.reset(profile=self.profile)
        state.settings["api_key"] = KEY

    def tearDown(self):
        shutil.rmtree(self.profile, ignore_errors=True)

    def run_addon(self, query, *answers):
        transport = FakeTransport(*answers)
        with mock.patch.object(api, "urllib_transport", transport):
            addon.run(["plugin://service.subtitles.subdl/", "7", "?" + query])
        self.assertEqual(state.ended, [7], "Kodi must always get endOfDirectory")
        self.assertNotIn(KEY, state.logged())
        for item in state.items:
            self.assertNotIn(KEY, item["url"])
        return transport

    def play_film(self):
        state.labels.update({"VideoPlayer.Title": "The Matrix", "VideoPlayer.Year": "1999",
                             "VideoPlayer.UniqueID(imdb)": "tt0133093", "VideoPlayer.UniqueID(tmdb)": "603"})
        state.playing_file = "/films/%s.mkv" % MATRIX

    def play_episode(self):
        state.labels.update({"VideoPlayer.Title": "Gray Matter", "VideoPlayer.TVShowTitle": "Breaking Bad",
                             "VideoPlayer.Season": "1", "VideoPlayer.Episode": "5",
                             "VideoPlayer.UniqueID(imdb)": "tt1054724", "VideoPlayer.TvShowDBID": "12"})
        state.tvshows[12] = {"uniqueid": {"imdb": "tt0903747", "tmdb": "1396", "tvdb": "81189"},
                             "year": 2008, "originaltitle": "Breaking Bad"}
        state.playing_file = "/tv/Breaking.Bad.S01E05.720p.BluRay.x264-DEMAND.mkv"

    def messages(self, kind):
        return [dialog[2] for dialog in state.dialogs if dialog[0] == kind]

    def row_link(self, index=0):
        return dict(parse_qsl(urlsplit(state.items[index]["url"]).query))


class SearchTest(FlowTest):
    def test_film_search_lists_preferred_language_and_exact_release_first(self):
        self.play_film()
        rows = [subtitle(1, language="EN", release_name="The.Matrix.1999.720p.WEB-DL-OTHER"),
                subtitle(2, language="FA", release_name="The.Matrix.1999.720p.WEB-DL-OTHER"),
                subtitle(3, language="FA", release_name=MATRIX, hi=True)]
        transport = self.run_addon("action=search&languages=English%2cPersian&preferredlanguage=Persian",
                                   response(200, search_body(rows)))

        self.assertEqual(transport.query(), {
            "type": "movie", "imdb_id": "tt0133093", "languages": "FA,EN", "subs_per_page": "30",
            "releases": "1", "api_key": KEY, "client": "kodi"})
        self.assertEqual(transport.requests[0].get_header("User-agent"),
                         "SubDL-Kodi/1.0.0 (service.subtitles.subdl; Kodi/21.2; Linux)")
        rows_shown = [(item["listitem"].label, item["listitem"].label2) for item in state.items]
        self.assertEqual(rows_shown, [("Persian", MATRIX), ("Persian", "The.Matrix.1999.720p.WEB-DL-OTHER"),
                                      ("English", "The.Matrix.1999.720p.WEB-DL-OTHER")])
        first = state.items[0]["listitem"]
        self.assertEqual(first.properties, {"sync": "true", "hearing_imp": "true"})
        self.assertEqual(first.art, {"icon": "5", "thumb": "fa"})
        self.assertEqual(self.row_link(), {"action": "download", "path": "/subtitle/3-1003.zip", "lang": "FA"})

    def test_id_not_found_falls_back_to_the_next_way(self):
        self.play_film()
        transport = self.run_addon("action=search&languages=English", response(200, TITLE_MISS),
                                   response(200, search_body([subtitle(1)])))
        self.assertEqual([request_query.get("imdb_id") or request_query.get("tmdb_id")
                          for request_query in (transport.query(0), transport.query(1))], ["tt0133093", "603"])
        self.assertEqual(len(state.items), 1)

    def test_title_from_another_year_is_not_trusted(self):
        state.labels.update({"VideoPlayer.Title": "Dune", "VideoPlayer.Year": "1984"})
        remake = {"sd_id": 9, "type": "movie", "name": "Dune", "year": 2021}
        transport = self.run_addon("action=search&languages=English",
                                   response(200, search_body([subtitle(1)], title=remake)))
        self.assertEqual(len(transport.requests), 1)
        self.assertEqual(state.items, [])
        self.assertIn("another year", state.logged())

    def test_episode_searches_the_show_and_takes_the_file_out_of_a_pack(self):
        self.play_episode()
        pack = subtitle(5, season=1, full_season=True, release_name="Breaking.Bad.S01.BluRay",
                        unpack_files=[pack_file("e4", "Breaking.Bad.S01E04.srt", 1, 4),
                                      pack_file("e5", "Breaking.Bad.S01E05.srt", 1, 5)])
        transport = self.run_addon("action=search&languages=English", response(200, search_body([pack])))
        self.assertEqual(transport.query(), {
            "type": "tv", "season_number": "1", "episode_number": "5", "imdb_id": "tt0903747",
            "languages": "EN", "subs_per_page": "30", "releases": "1", "unpack": "1", "api_key": KEY,
            "client": "kodi"})
        self.assertEqual(state.items[0]["listitem"].label2, "Breaking.Bad.S01E05  [Season pack]")
        self.assertEqual(self.row_link(), {"action": "download", "path": "/subtitle/packnid/e5", "lang": "EN",
                                           "format": "srt", "season": "1", "episode": "5"})

    def test_manual_search_for_an_episode(self):
        transport = self.run_addon("action=manualsearch&searchstring=Breaking%20Bad%20S01E05&languages=English",
                                   response(200, search_body([])))
        query = transport.query()
        self.assertEqual((query["film_name"], query["type"], query["season_number"], query["episode_number"]),
                         ("Breaking Bad", "tv", "1", "5"))

    def test_second_page_is_read_when_the_first_has_no_exact_release(self):
        self.play_film()
        first = search_body([subtitle(1, release_name="The.Matrix.1999.720p.WEB-DL-OTHER")], pages=4)
        second = search_body([subtitle(2, release_name=MATRIX)], pages=4)
        transport = self.run_addon("action=search&languages=English", response(200, first), response(200, second))
        self.assertEqual(transport.query(1)["page"], "2")
        self.assertEqual(len(transport.requests), 2)
        self.assertEqual(self.row_link()["path"], "/subtitle/2-1002.zip")

    def test_languages_subdl_does_not_have(self):
        self.play_film()
        transport = self.run_addon("action=search&languages=Welsh")
        self.assertEqual(transport.requests, [])
        self.assertEqual(self.messages("notification"), [state.strings[32211]])


class MessageTest(FlowTest):
    def test_missing_key_explains_where_to_get_one_and_offers_settings(self):
        state.settings["api_key"] = ""
        state.yesno_answer = True
        transport = self.run_addon("action=search&languages=English")
        self.assertEqual(transport.requests, [])
        dialog = state.dialogs[0]
        self.assertEqual(dialog[0], "yesno")
        self.assertIn(PANEL, dialog[2])
        self.assertEqual((dialog[3], dialog[4]), ("Close", "Open settings"))
        self.assertEqual(state.opened_settings, 1)

        state.dialogs, state.ended = [], []
        self.run_addon("action=search&languages=English")
        self.assertEqual(state.dialogs, [("notification", "API key needed", PANEL)])

    def test_refused_key(self):
        self.play_film()
        refused = response(403, {"status": False, "error": "not_authorized", "message": "Not Authorized"})
        self.run_addon("action=search&languages=English", refused)
        self.assertIn(PANEL, self.messages("yesno")[0])
        self.assertIn("did not accept", self.messages("yesno")[0])

        state.dialogs, state.ended = [], []
        self.run_addon("action=search&languages=English", refused)
        self.assertEqual(state.dialogs, [("notification", "API key not accepted", PANEL)])

    def test_daily_search_limit_shows_the_link_once_then_a_short_notice(self):
        self.play_film()
        limit = response(429, {"status": False, "error": "daily_limit", "message": "Daily Limit"})
        self.run_addon("action=search&languages=English", limit)
        self.assertEqual(self.messages("ok"), [state.strings[32205]])
        self.assertIn(PANEL, state.strings[32205])

        state.dialogs, state.ended = [], []
        self.run_addon("action=search&languages=English", limit)
        self.assertEqual(state.dialogs, [("notification", "Daily limit reached", PANEL)])

    def test_a_new_key_gets_the_dialog_again(self):
        self.play_film()
        limit = response(429, {"status": False, "error": "daily_limit"})
        self.run_addon("action=search&languages=English", limit)
        state.settings["api_key"] = KEY + "-new"
        state.dialogs, state.ended = [], []
        self.run_addon("action=search&languages=English", limit)
        self.assertEqual(len(self.messages("ok")), 1)

    def test_unexpected_failure_still_answers_kodi(self):
        self.play_film()
        with mock.patch("subdl.results.build_entries", side_effect=ValueError("boom")):
            self.run_addon("action=search&languages=English", response(200, search_body([subtitle(1)])))
        self.assertEqual(self.messages("notification"), [state.strings[32216]])
        self.assertIn("ValueError at", state.logged())
        self.assertNotIn("boom", state.logged())


class DownloadTest(FlowTest):
    def downloaded(self):
        self.assertEqual(len(state.items), 1)
        path = state.items[0]["url"]
        with open(path, "rb") as handle:
            return path, handle.read()

    def test_zip_is_unpacked_into_a_fresh_folder_for_kodi(self):
        self.play_film()
        archive_bytes = zip_bytes({MATRIX + ".srt": SRT, "readme.txt": b"hello"})
        transport = self.run_addon("action=download&path=%2Fsubtitle%2F3-1003.zip&lang=FA",
                                   response(200, archive_bytes))
        self.assertEqual(transport.requests[0].full_url,
                         "https://dl.subdl.com/subtitle/3-1003.zip?api_key=" + KEY)
        path, data = self.downloaded()
        self.assertEqual(data, SRT)
        self.assertEqual(os.path.basename(path), MATRIX + ".srt")
        self.assertEqual(os.path.dirname(os.path.dirname(path)), os.path.join(self.profile, "temp"))

    def test_single_file_from_a_pack(self):
        self.play_episode()
        answer = response(200, SRT, {"Content-Disposition": "attachment; filename=\"Breaking.Bad.S01E05.srt\""})
        self.run_addon("action=download&path=%2Fsubtitle%2Fpacknid%2Fe5&lang=EN&format=srt&season=1&episode=5",
                       answer)
        path, data = self.downloaded()
        self.assertEqual((os.path.basename(path), data), ("Breaking.Bad.S01E05.srt", SRT))

    def test_whole_pack_gives_kodi_the_episode(self):
        self.play_episode()
        pack = zip_bytes({"S01/Breaking.Bad.S01E04.srt": b"4", "S01/Breaking.Bad.S01E05.srt": SRT})
        self.run_addon("action=download&path=%2Fsubtitle%2F5-1005.zip&lang=EN&pack=1&season=1&episode=5",
                       response(200, pack))
        path, data = self.downloaded()
        self.assertEqual((os.path.basename(path), data), ("Breaking.Bad.S01E05.srt", SRT))

    def test_pack_without_the_episode(self):
        self.play_episode()
        pack = zip_bytes({"Breaking.Bad.S01E04.srt": SRT})
        self.run_addon("action=download&path=%2Fsubtitle%2F5-1005.zip&lang=EN&pack=1&season=1&episode=5",
                       response(200, pack))
        self.assertEqual(state.items, [])
        self.assertEqual(self.messages("notification"), [state.strings[32213]])

    def test_daily_download_limit(self):
        body = {"error": "api_download_limit_exceeded", "message": "Free daily download limit reached (50/day)."}
        self.run_addon("action=download&path=%2Fsubtitle%2F1-2.zip&lang=EN", response(429, body))
        self.assertEqual(self.messages("ok"), [state.strings[32206]])
        self.assertIn(PANEL, state.strings[32206])

    def test_paths_off_subdl_are_never_fetched(self):
        transport = self.run_addon("action=download&path=https%3A%2F%2Fevil.example%2Fsubtitle%2F1-2.zip")
        self.assertEqual(transport.requests, [])
        self.assertEqual(self.messages("notification"), [state.strings[32212]])

    def test_unreadable_download(self):
        self.run_addon("action=download&path=%2Fsubtitle%2F1-2.zip&lang=EN", response(200, b"Rar!\x1a\x07\x00"))
        self.assertEqual(self.messages("notification"), [state.strings[32214]])

    def test_old_temp_folders_are_cleared_and_recent_ones_kept(self):
        temp = os.path.join(self.profile, "temp")
        old, recent = os.path.join(temp, "old"), os.path.join(temp, "recent")
        os.makedirs(old)
        os.makedirs(recent)
        hours_ago = time.time() - 2 * 3600
        os.utime(old, (hours_ago, hours_ago))
        self.run_addon("action=download&path=%2Fsubtitle%2F1-2.zip&lang=EN", response(200, zip_bytes({"a.srt": SRT})))
        self.assertFalse(os.path.exists(old))
        self.assertTrue(os.path.exists(recent))


class CheckKeyTest(FlowTest):
    def check(self, *answers):
        transport = FakeTransport(*answers)
        with mock.patch.object(api, "urllib_transport", transport):
            addon.check_key()
        return transport

    def test_working_free_key(self):
        body = {"status": True, "user": {"id": 1, "name": "Viewer", "username": "viewer"},
                "apiAccount": {"requests": {"today": 12, "limit": 2000}, "downloads": {"today": 3, "limit": 0}},
                "pro": {"isPaid": False, "plan": None}}
        transport = self.check(response(200, body))
        self.assertEqual(transport.path(), "/api/v1/me")
        self.assertEqual(state.dialogs, [("ok", "Your SubDL API key works", "[CR]".join([
            "Account: viewer", "Plan: Free", "Searches today: 12 of 2,000", "Downloads today: 3"]))])

    def test_paid_key(self):
        body = {"status": True, "user": {"username": "payer"}, "pro": {"isPaid": True, "plan": {"name": "SubDL Pro"}},
                "apiAccount": {"requests": {"today": 1, "limit": 30000}, "downloads": {"today": 0, "limit": 2000}}}
        self.check(response(200, body))
        self.assertIn("Plan: SubDL Pro", self.messages("ok")[0])
        self.assertIn("Downloads today: 0 of 2,000", self.messages("ok")[0])

    def test_missing_key_always_shows_the_dialog(self):
        state.settings["api_key"] = ""
        for _ in range(2):
            self.check()
        self.assertEqual(len(self.messages("yesno")), 2)
        self.assertIn(PANEL, self.messages("yesno")[0])

    def test_button_script_runs_outside_the_addon_context(self):
        # Kodi starts check_key.py with RunScript(path): Addon() without an id raises there.
        state.in_addon_context = False
        body = {"status": True, "user": {"username": "viewer"}, "pro": {"isPaid": False},
                "apiAccount": {"requests": {"today": 1, "limit": 2000}, "downloads": {"today": 0}}}
        with mock.patch.object(api, "urllib_transport", FakeTransport(response(200, body))):
            runpy.run_path(os.path.join(ADDON_DIR, "check_key.py"), run_name="__main__")
        self.assertEqual(state.dialogs[0][:2], ("ok", "Your SubDL API key works"))


class EntryPointTest(FlowTest):
    def test_service_py_runs_a_search_and_answers_kodi(self):
        argv = ["plugin://service.subtitles.subdl/", "3", "?action=search&languages=Welsh", "resume:false"]
        with mock.patch.object(sys, "argv", argv):
            runpy.run_path(os.path.join(ADDON_DIR, "service.py"), run_name="__main__")
        self.assertEqual(state.ended, [3])
        self.assertEqual(self.messages("notification"), [state.strings[32211]])


if __name__ == "__main__":
    unittest.main()
