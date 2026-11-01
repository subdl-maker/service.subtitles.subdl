import unittest

from tests import support  # noqa: F401 - sets up import paths

from subdl import languages


class LanguagesTest(unittest.TestCase):
    def test_kodi_codes_to_subdl_codes(self):
        self.assertEqual(languages.subdl_codes(["en", "fa", "pb"]), ["EN", "FA", "BR_PT"])
        self.assertEqual(languages.subdl_codes(["zh"]), ["ZH", "ZH_BG"])
        self.assertEqual(languages.subdl_codes(["sr", "fr"]), ["SR", "SR_CYRL", "FR", "FR_CA"])
        self.assertEqual(languages.subdl_codes(["pt"]), ["PT"])
        self.assertEqual(languages.subdl_codes(["mni", "iw", "nb", "nn", "jw"]), ["MNI", "HE", "NO", "JV"])

    def test_unknown_and_repeated_codes_are_dropped(self):
        # SubDL ignores unknown codes, and a request left with none returns every language.
        self.assertEqual(languages.subdl_codes(["cy", "", None, "EN", "en"]), ["EN"])

    def test_every_subdl_code_is_reachable_from_kodi(self):
        reachable = set(languages.subdl_codes(iso for iso, _ in languages.SUBDL_LANGUAGES.values()))
        self.assertEqual(reachable, set(languages.SUBDL_LANGUAGES) - {"JW"})

    def test_subdl_code_to_kodi(self):
        self.assertEqual(languages.iso_for("BR_PT"), "pb")
        self.assertEqual(languages.iso_for("br-pt"), "pb")
        self.assertEqual(languages.iso_for("ZH_BG"), "zh")
        self.assertEqual(languages.iso_for("HU_EN"), "hu")  # two-language subtitle: first language
        self.assertEqual(languages.iso_for("XX"), "")
        self.assertEqual(languages.english_name("FA"), "Persian")
        self.assertEqual(languages.english_name("XX"), "XX")

    def test_same_language(self):
        self.assertTrue(languages.same_language("ZH", "ZH_BG"))
        self.assertTrue(languages.same_language("JV", "JW"))
        self.assertFalse(languages.same_language("PT", "BR_PT"))
        self.assertFalse(languages.same_language("XX", "YY"))

    def test_iso_for_name(self):
        self.assertEqual(languages.iso_for_name("Portuguese (Brazil)"), "pb")
        self.assertEqual(languages.iso_for_name(" persian "), "fa")
        self.assertEqual(languages.iso_for_name("Bengali; Bangla"), "bn")
        self.assertEqual(languages.iso_for_name("Klingon"), "")


if __name__ == "__main__":
    unittest.main()
