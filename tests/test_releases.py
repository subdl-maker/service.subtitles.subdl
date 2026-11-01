import unittest

from tests import support  # noqa: F401 - sets up import paths

from subdl import releases


class NameFromPathTest(unittest.TestCase):
    def test_local_and_network_files(self):
        self.assertEqual(releases.name_from_path("/media/Films/The.Matrix.1999.1080p.BluRay.x264-GROUP.mkv"),
                         "The.Matrix.1999.1080p.BluRay.x264-GROUP")
        self.assertEqual(releases.name_from_path("smb://nas/tv/Show.S01E02.720p.HDTV.x264-KILLERS.mp4"),
                         "Show.S01E02.720p.HDTV.x264-KILLERS")
        self.assertEqual(releases.name_from_path("C:\\Films\\Some Film (2010) 1080p.mkv"), "Some Film (2010) 1080p")

    def test_streams_and_wrappers(self):
        self.assertEqual(releases.name_from_path(
            "https://cdn.example/d/AbC/The.Matrix.1999.2160p.WEB-DL.mkv?token=secret"),
            "The.Matrix.1999.2160p.WEB-DL")
        self.assertEqual(releases.name_from_path(
            "stack:///films/Film.2001.CD1.avi , /films/Film.2001.CD2.avi"), "Film.2001.CD1")
        self.assertEqual(releases.name_from_path("rar://%2fdl%2fpack.rar/Film.2001.DVDRip.XviD-GRP.avi"),
                         "Film.2001.DVDRip.XviD-GRP")

    def test_names_that_mean_nothing(self):
        for path in ("", "plugin://plugin.video.x/play/1", "pvr://channels/tv/1.pvr",
                     "https://host/play?id=1", "/media/movie.mkv"):
            self.assertEqual(releases.name_from_path(path), "", path)


class EpisodeTest(unittest.TestCase):
    def test_parse_episode(self):
        self.assertEqual(releases.parse_episode("Show.S01E02.720p"), (1, 2))
        self.assertEqual(releases.parse_episode("show s1.e102"), (1, 102))
        self.assertEqual(releases.parse_episode("Show 3x07 HDTV"), (3, 7))
        self.assertEqual(releases.parse_episode("Show Season 2 Episode 5"), (2, 5))
        self.assertIsNone(releases.parse_episode("Film.2010.1080p.x264"))
        self.assertIsNone(releases.parse_episode("Film 1920x1080"))

    def test_episode_match(self):
        self.assertEqual(releases.episode_match("Show.S01E05.srt", 1, 5), 3)
        self.assertEqual(releases.episode_match("Show.S01E05.srt", None, 5), 3)
        self.assertEqual(releases.episode_match("Show.S02E05.srt", 1, 5), -1)
        self.assertEqual(releases.episode_match("Show.S01E06.srt", 1, 5), -1)
        self.assertEqual(releases.episode_match("Show - Episode 5.srt", 1, 5), 2)
        self.assertEqual(releases.episode_match("Show EP06.srt", 1, 5), -1)
        self.assertEqual(releases.episode_match("[Group] Show - 05 [1080p].ass", 1, 5), 1)
        self.assertEqual(releases.episode_match("Show.Complete.srt", 1, 5), 0)
        self.assertEqual(releases.episode_match("Show.1080p.x264.srt", 1, 108), 0)

    def test_parse_year(self):
        self.assertEqual(releases.parse_year("2001.A.Space.Odyssey.1968.1080p"), 1968)
        self.assertEqual(releases.parse_year("Blade.Runner.2049.2017.2160p"), 2017)
        self.assertIsNone(releases.parse_year("Film.1080p"))


class ScoreTest(unittest.TestCase):
    VIDEO = "The.Matrix.1999.1080p.BluRay.x264-GROUP"

    def test_exact_release_ignores_case_separators_and_tags(self):
        self.assertTrue(releases.is_exact(self.VIDEO, "the matrix 1999 1080p bluray x264 group.srt"))
        self.assertTrue(releases.is_exact(self.VIDEO + "[rarbg]", self.VIDEO))
        self.assertEqual(releases.score(self.VIDEO, self.VIDEO + ".srt"), 100)

    def test_closer_releases_score_higher(self):
        same_group = releases.score(self.VIDEO, "The.Matrix.1999.720p.BluRay.x264-GROUP")
        same_source = releases.score(self.VIDEO, "The.Matrix.1999.1080p.BluRay.x265-OTHER")
        other_source = releases.score(self.VIDEO, "The.Matrix.1999.1080p.WEB-DL.DDP5.1.H.264-OTHER")
        self.assertGreater(same_group, same_source)
        self.assertGreater(same_source, other_source)
        self.assertLess(same_group, 90)

    def test_web_dl_is_not_a_release_group(self):
        self.assertEqual(releases._group("Film.2010.1080p.WEB-DL"), "")
        self.assertEqual(releases._group("Film.2010.1080p.WEB-DL-NTb[eztv].mkv"), "ntb")

    def test_no_video_name_scores_nothing(self):
        self.assertEqual(releases.score("", "anything"), 0)
        self.assertEqual(releases.best_score(self.VIDEO, ["", "Unrelated.Name"]), releases.score(
            self.VIDEO, "Unrelated.Name"))


if __name__ == "__main__":
    unittest.main()
