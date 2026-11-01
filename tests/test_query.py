import unittest

from tests import support  # noqa: F401 - sets up import paths

from subdl.query import PlayingItem, build_manual_plan, build_plan, imdb_id


def kinds(plan):
    return [(attempt.kind, attempt.params) for attempt in plan]


class MoviePlanTest(unittest.TestCase):
    def test_library_film_tries_ids_then_names_then_file(self):
        item = PlayingItem(title="The Matrix", original_title="The Matrix", year=1999, imdb_id="tt0133093",
                           tmdb_id="603", filename="The.Matrix.1999.1080p.BluRay.x264-GROUP")
        plan = build_plan(item)
        self.assertEqual(kinds(plan), [
            ("imdb", {"type": "movie", "imdb_id": "tt0133093"}),
            ("tmdb", {"type": "movie", "tmdb_id": "603"}),
            ("title", {"type": "movie", "film_name": "The Matrix"}),
            ("filename", {"file_name": "The.Matrix.1999.1080p.BluRay.x264-GROUP"}),
        ])
        self.assertEqual([attempt.expect_year for attempt in plan], [None, None, 1999, 1999])
        self.assertTrue(all(attempt.episode is None for attempt in plan))

    def test_digits_are_never_read_as_an_imdb_id(self):
        # Kodi's IMDBNumber holds the TMDB id when TMDB is the default scraper.
        plan = build_plan(PlayingItem(title="The Matrix", imdb_id="603"))
        self.assertEqual(kinds(plan), [("title", {"type": "movie", "film_name": "The Matrix"})])
        self.assertEqual(imdb_id("tt0133093 "), "tt0133093")
        self.assertEqual(imdb_id("0133093"), "")

    def test_title_that_is_only_the_file_name_is_left_to_the_file_search(self):
        name = "The.Matrix.1999.1080p.BluRay.x264-GROUP"
        plan = build_plan(PlayingItem(title=name, filename=name))
        self.assertEqual(kinds(plan), [("filename", {"file_name": name})])
        self.assertEqual(plan[0].expect_year, 1999)

    def test_original_title_is_tried_when_different(self):
        plan = build_plan(PlayingItem(title="Le Fabuleux Destin", original_title="Amelie", year=2001))
        self.assertEqual([attempt.params.get("film_name") for attempt in plan], ["Le Fabuleux Destin", "Amelie"])

    def test_nothing_known(self):
        self.assertEqual(build_plan(PlayingItem()), [])


class EpisodePlanTest(unittest.TestCase):
    def test_library_episode_searches_the_show(self):
        item = PlayingItem(title="Pilot", tvshow="Breaking Bad", season=1, episode=1, imdb_id="tt0959621",
                           show_imdb_id="tt0903747", show_tmdb_id="1396", tvshow_year=2008, from_library=True)
        plan = build_plan(item)
        episode = {"type": "tv", "season_number": "1", "episode_number": "1"}
        self.assertEqual(kinds(plan), [
            ("imdb", dict(episode, imdb_id="tt0903747")),
            ("tmdb", dict(episode, tmdb_id="1396")),
            ("title", dict(episode, film_name="Breaking Bad")),
        ])
        self.assertEqual(plan[2].expect_year, 2008)
        self.assertTrue(all(attempt.episode == (1, 1) for attempt in plan))

    def test_episode_imdb_from_an_addon_is_tried_once(self):
        item = PlayingItem(tvshow="Breaking Bad", season=1, episode=1, imdb_id="tt0903747")
        self.assertEqual(kinds(build_plan(item))[0],
                         ("imdb", {"type": "tv", "season_number": "1", "episode_number": "1", "imdb_id": "tt0903747"}))

    def test_episode_known_only_from_the_file_name(self):
        name = "Breaking.Bad.S02E03.720p.HDTV.x264-CTU"
        item = PlayingItem(title=name, filename=name)
        self.assertTrue(item.is_episode)
        self.assertEqual(kinds(build_plan(item)), [
            ("filename", {"type": "tv", "season_number": "2", "episode_number": "3", "file_name": name}),
        ])

    def test_specials_keep_season_zero(self):
        plan = build_plan(PlayingItem(tvshow="Doctor Who", season=0, episode=3))
        self.assertEqual(plan[0].params["season_number"], "0")
        self.assertEqual(plan[0].episode, (0, 3))


class ManualPlanTest(unittest.TestCase):
    def test_imdb_id(self):
        self.assertEqual(kinds(build_manual_plan(" tt0133093 ")), [("manual", {"imdb_id": "tt0133093"})])

    def test_episode_in_the_text(self):
        for text, name in (("Breaking Bad S02E05", "Breaking Bad"), ("Breaking Bad 2x05", "Breaking Bad"),
                           ("breaking bad - s2e5", "breaking bad")):
            plan = build_manual_plan(text)
            self.assertEqual(plan[0].params, {"type": "tv", "season_number": "2", "episode_number": "5",
                                              "film_name": name}, text)
            self.assertEqual(plan[0].episode, (2, 5))

    def test_titles_ending_in_a_number(self):
        plan = build_manual_plan("Blade Runner 2049")
        self.assertEqual([attempt.params["film_name"] for attempt in plan], ["Blade Runner 2049", "Blade Runner"])
        self.assertEqual([attempt.expect_year for attempt in plan], [None, 2049])
        plan = build_manual_plan("The Matrix (1999)")
        self.assertEqual([attempt.params["film_name"] for attempt in plan], ["The Matrix (1999)", "The Matrix"])
        self.assertEqual(kinds(build_manual_plan("1917")), [("manual", {"film_name": "1917"})])

    def test_plain_text_while_an_episode_plays_keeps_its_episode(self):
        playing = PlayingItem(tvshow="Shameless (US)", season=3, episode=4)
        plan = build_manual_plan("Shameless", playing)
        self.assertEqual(plan[0].params, {"type": "tv", "season_number": "3", "episode_number": "4",
                                          "film_name": "Shameless"})
        self.assertEqual(plan[0].episode, (3, 4))

    def test_empty_text(self):
        self.assertEqual(build_manual_plan("   "), [])


if __name__ == "__main__":
    unittest.main()
