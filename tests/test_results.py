import unittest

from tests.support import KEY, pack_file, subtitle

from subdl import results

VIDEO = "The.Matrix.1999.1080p.BluRay.x264-GROUP"


class LanguageAndOrderTest(unittest.TestCase):
    def test_preferred_language_first_then_exact_release(self):
        rows = [
            subtitle(1, language="EN", release_name="The.Matrix.1999.720p.WEB-DL-OTHER"),
            subtitle(2, language="FA", release_name="The.Matrix.1999.720p.WEB-DL-OTHER"),
            subtitle(3, language="EN", release_name=VIDEO),
            subtitle(4, language="FA", release_name=VIDEO),
        ]
        entries = results.build_entries(rows, ["FA", "EN"], VIDEO)
        self.assertEqual([(e.language, e.sync) for e in entries],
                         [("FA", True), ("FA", False), ("EN", True), ("EN", False)])
        self.assertEqual(entries[0].rating, 5)

    def test_unwanted_languages_are_dropped_and_keys_stripped(self):
        rows = [subtitle(1, language="EN"), subtitle(2, language="DE")]
        entries = results.build_entries(rows, ["EN"])
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].path, "/subtitle/1-1001.zip")
        self.assertNotIn(KEY, entries[0].path)

    def test_second_language_of_a_two_language_subtitle_counts(self):
        rows = [subtitle(1, language="HU", secondary_language="EN")]
        entry = results.build_entries(rows, ["EN"])[0]
        self.assertEqual((entry.language, entry.secondary), ("EN", "HU"))

    def test_shared_kodi_language(self):
        rows = [subtitle(1, language="ZH_BG"), subtitle(2, language="JW")]
        self.assertEqual([e.language for e in results.build_entries(rows, ["ZH", "JV"])], ["ZH_BG", "JW"])

    def test_release_list_counts_toward_the_match(self):
        rows = [subtitle(1, release_name="Matrix", releases=["Something.Else", VIDEO])]
        self.assertTrue(results.build_entries(rows, ["EN"], VIDEO)[0].sync)

    def test_duplicates_and_bad_rows(self):
        rows = [subtitle(1), subtitle(1), "junk", subtitle(2, url="https://evil.example/subtitle/2-3.zip"),
                subtitle(3, url="/s/info/abc")]
        self.assertEqual(len(results.build_entries(rows, ["EN"])), 1)

    def test_hearing_impaired_filter(self):
        rows = [subtitle(1, hi=True), subtitle(2, hi=False)]
        self.assertEqual(len(results.build_entries(rows, ["EN"])), 2)
        self.assertEqual([e.hearing_impaired for e in results.build_entries(rows, ["EN"], hearing_impaired=1)],
                         [False])
        self.assertEqual([e.hearing_impaired for e in results.build_entries(rows, ["EN"], hearing_impaired=2)],
                         [True])

    def test_ordered_codes(self):
        self.assertEqual(results.ordered_codes(["EN", "FA", "ZH", "ZH_BG"], ["ZH", "ZH_BG"]),
                         ["ZH", "ZH_BG", "EN", "FA"])
        self.assertEqual(results.ordered_codes(["EN"], ["FA"]), ["EN"])

    def test_page_count(self):
        self.assertEqual(results.page_count({"totalPages": 3}), 3)
        self.assertEqual(results.page_count({}), 1)


class EpisodeTest(unittest.TestCase):
    TARGET = (1, 5)

    def test_wrong_season_or_episode_is_dropped(self):
        rows = [
            subtitle(1, season=1, episode=5, episode_from=5, episode_end=5, release_name="Show.S01E05"),
            subtitle(2, season=2, episode=5, episode_from=5, episode_end=5),
            subtitle(3, season=1, episode=6, episode_from=6, episode_end=6),
            subtitle(4, season=1, episode=5, episode_from=5, episode_end=5, release_name="Show.S01E04.WEB"),
        ]
        entries = results.build_entries(rows, ["EN"], target=self.TARGET)
        self.assertEqual([e.path for e in entries], ["/subtitle/1-1001.zip"])

    def test_episode_file_is_taken_out_of_an_indexed_pack(self):
        files = [pack_file("f4", "Show.S01E04.WEB.srt", 1, 4), pack_file("f5", "Show.S01E05.WEB.srt", 1, 5)]
        rows = [subtitle(1, season=1, episode=None, full_season=True, release_name="Show.S01.WEB",
                         unpack_files=files)]
        entry = results.build_entries(rows, ["EN"], "Show.S01E05.WEB", target=self.TARGET)[0]
        self.assertEqual(entry.path, "/subtitle/packnid/f5")
        self.assertEqual((entry.pack_file, entry.pack, entry.format), (True, False, "srt"))
        self.assertEqual(entry.release, "Show.S01E05.WEB")
        self.assertTrue(entry.sync)

    def test_indexed_pack_without_the_episode_is_dropped(self):
        files = [pack_file("f4", "a.srt", 1, 4), pack_file("f6", "b.srt", 1, 6)]
        rows = [subtitle(1, season=1, full_season=True, unpack_files=files)]
        self.assertEqual(results.build_entries(rows, ["EN"], target=self.TARGET), [])

    def test_legacy_pack_files_are_matched_by_name(self):
        files = [pack_file("", "Show.S01E05.srt", 0, 0), pack_file("", "Show.S01E06.srt", 0, 0)]
        files[0]["url"] = "/mobile/nid?hash=aaa&api_key=" + KEY
        files[1]["url"] = "/mobile/nid?hash=bbb&api_key=" + KEY
        rows = [subtitle(1, season=1, episode_from=1, episode_end=10, unpack_files=files)]
        entry = results.build_entries(rows, ["EN"], target=self.TARGET)[0]
        self.assertEqual(entry.path, "/mobile/nid?hash=aaa")

    def test_pack_without_a_file_list_is_downloaded_whole_and_listed_last(self):
        rows = [subtitle(1, season=1, full_season=True, release_name="Show.S01.Complete"),
                subtitle(2, season=1, episode=5, episode_from=5, episode_end=5, release_name="Show.S01E05")]
        entries = results.build_entries(rows, ["EN"], target=self.TARGET)
        self.assertEqual([(e.path, e.pack) for e in entries],
                         [("/subtitle/2-1002.zip", False), ("/subtitle/1-1001.zip", True)])

    def test_packs_can_be_switched_off(self):
        rows = [subtitle(1, season=1, full_season=True)]
        self.assertEqual(results.build_entries(rows, ["EN"], target=self.TARGET, include_packs=False), [])


class LanguageGroupsTest(unittest.TestCase):
    def test_one_search_per_kodi_language(self):
        self.assertEqual(results.language_groups(["FA", "EN"]), [["FA"], ["EN"]])
        self.assertEqual(results.language_groups(["EN", "ZH", "ZH_BG", "SR", "SR_CYRL"]),
                         [["EN"], ["ZH", "ZH_BG"], ["SR", "SR_CYRL"]])

    def test_languages_past_the_limit_share_the_last_search(self):
        self.assertEqual(results.language_groups(["EN", "FR", "FR_CA", "DE", "ES"], limit=2),
                         [["EN"], ["FR", "FR_CA", "DE", "ES"]])
        codes = ["EN", "FA", "AR", "DE", "ES", "IT"]
        self.assertEqual(len(results.language_groups(codes)), 6)
        self.assertEqual(results.language_groups(codes + ["PT"])[-1], ["IT", "PT"])


if __name__ == "__main__":
    unittest.main()
