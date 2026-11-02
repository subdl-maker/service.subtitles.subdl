import io
import os
import shutil
import tempfile
import unittest
import zipfile

from tests.support import SRT, zip_bytes

from subdl import archive
from subdl.archive import ArchiveError, SubtitleFile


def names(files):
    return [item.name for item in files]


def mark_encrypted(data, filename):
    """Set the "encrypted" flag on one entry's central directory record.

    Python's zipfile cannot write encrypted entries, and it reads the flag from the
    central directory, so flipping that bit is enough to look like one.
    """
    data = bytearray(data)
    start = data.find(b"PK\x01\x02")
    while start != -1:
        length = int.from_bytes(data[start + 28:start + 30], "little")
        if bytes(data[start + 46:start + 46 + length]) == filename:
            data[start + 8] |= 0x1
        start = data.find(b"PK\x01\x02", start + 4)
    return bytes(data)


class FilesInTest(unittest.TestCase):
    def test_zip_with_one_subtitle_and_clutter(self):
        data = zip_bytes({"Film.2010.srt": SRT, "readme.txt": b"Downloaded from somewhere", "site.url": b"x",
                          "folder/": b"", ".hidden.srt": SRT})
        self.assertEqual(names(archive.files_in(data)), ["Film.2010.srt"])

    def test_txt_with_subtitle_timings_is_kept(self):
        data = zip_bytes({"film.txt": b"{100}{200}Hello|World"})
        self.assertEqual(names(archive.files_in(data)), ["film.txt"])

    def test_paths_inside_the_archive_cannot_escape(self):
        data = zip_bytes({"../../etc/evil.srt": SRT, "sub\\..\\..\\win.srt": SRT, "a/b/c.ass": SRT})
        self.assertEqual(sorted(names(archive.files_in(data))), ["c.ass", "evil.srt", "win.srt"])

    def test_nested_zip_one_level(self):
        inner = zip_bytes({"Inner.srt": SRT})
        deeper = zip_bytes({"deep.zip": zip_bytes({"Deep.srt": SRT})})
        data = zip_bytes({"inner.zip": inner, "deeper.zip": deeper, "Outer.srt": SRT})
        self.assertEqual(sorted(names(archive.files_in(data))), ["Inner.srt", "Outer.srt"])

    def test_oversized_and_encrypted_entries_are_skipped(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as handle:
            handle.writestr("big.srt", b"1" * (archive.MAX_FILE_BYTES + 1))
            handle.writestr("ok.srt", SRT)
            handle.writestr("locked.srt", b"scrambled")
        self.assertEqual(names(archive.files_in(mark_encrypted(buffer.getvalue(), b"locked.srt"))), ["ok.srt"])

    def test_vobsub_keeps_its_idx(self):
        data = zip_bytes({"Film.sub": b"\x00\x00\x01\xba", "Film.idx": b"# VobSub index file"})
        files = archive.files_in(data)
        self.assertEqual(names(files), ["Film.sub"])
        self.assertEqual(files[0].idx, b"# VobSub index file")

    def test_plain_subtitle_file(self):
        self.assertEqual(names(archive.files_in(SRT, "Show.S01E05.srt")), ["Show.S01E05.srt"])
        self.assertEqual(names(archive.files_in(SRT, "", "ass")), ["subtitle.ass"])
        self.assertEqual(names(archive.files_in(SRT, "download.bin", "")), ["subtitle.srt"])

    def test_unsupported_and_broken_downloads(self):
        for data in (b"Rar!\x1a\x07\x00rest", b"7z\xbc\xaf\x27\x1crest", b"PK\x03\x04broken", b"   "):
            with self.assertRaises(ArchiveError):
                archive.files_in(data, "x.srt")


class ChooseTest(unittest.TestCase):
    def test_episode_files_from_a_pack(self):
        files = [SubtitleFile("Show.S01E04.srt", SRT), SubtitleFile("Show.S01E05.srt", SRT),
                 SubtitleFile("Show.S01E05.ass", SRT)]
        self.assertEqual(names(archive.for_episode(files, 1, 5)), ["Show.S01E05.srt", "Show.S01E05.ass"])
        # The same subtitle in two formats: SubRip wins without asking.
        self.assertEqual(names(archive.choose(files, "", (1, 5))), ["Show.S01E05.srt"])
        self.assertEqual(archive.for_episode(files, 2, 5), [])

    def test_unnamed_files_are_kept_for_an_episode(self):
        files = [SubtitleFile("english.srt", SRT)]
        self.assertEqual(names(archive.choose(files, "", (1, 5))), ["english.srt"])

    def test_closest_release_wins(self):
        files = [SubtitleFile("Film.2010.720p.WEB-DL-OTHER.srt", SRT),
                 SubtitleFile("Film.2010.1080p.BluRay.x264-GROUP.srt", SRT)]
        chosen = archive.choose(files, "Film.2010.1080p.BluRay.x264-GROUP")
        self.assertEqual(names(chosen), ["Film.2010.1080p.BluRay.x264-GROUP.srt"])

    def test_viewer_is_asked_when_names_do_not_decide(self):
        files = [SubtitleFile("english.srt", SRT), SubtitleFile("english-sdh.srt", SRT)]
        asked = []

        def ask(options):
            asked.append(options)
            return 1

        chosen = archive.choose(files, "", ask=ask)
        self.assertEqual(len(asked), 1)
        self.assertEqual(names(chosen), [asked[0][1]])
        self.assertEqual(archive.choose(files, "", ask=lambda options: -1), [])

    def test_cd_parts_for_a_stacked_video(self):
        files = [SubtitleFile("Film.CD2.srt", SRT), SubtitleFile("Film.CD1.srt", SRT)]
        self.assertEqual(names(archive.choose(files, "", stacked=True)), ["Film.CD1.srt", "Film.CD2.srt"])
        self.assertEqual(archive.cd_parts([SubtitleFile("Film.CD1.srt", SRT), SubtitleFile("x.srt", SRT)]), [])
        self.assertEqual(archive.cd_parts([SubtitleFile("a.CD1.srt", SRT), SubtitleFile("a.CD3.srt", SRT)]), [])

    def test_nothing_to_choose(self):
        self.assertEqual(archive.choose([], "Film"), [])


class AsUtf8Test(unittest.TestCase):
    def test_utf8_and_bom_files_are_left_alone(self):
        utf8 = "باید".encode("utf-8")
        self.assertEqual(archive.as_utf8(utf8, "FA"), utf8)
        self.assertEqual(archive.as_utf8(b"\xef\xbb\xbf" + utf8, "FA"), b"\xef\xbb\xbf" + utf8)
        utf16 = "باید".encode("utf-16")
        self.assertEqual(archive.as_utf8(utf16, "FA"), utf16)
        self.assertEqual(archive.as_utf8(SRT, "EN"), SRT)

    def test_each_language_uses_its_code_page(self):
        for code, text, codec in (
            ("AR", "مرحبا يا كريم", "cp1256"), ("HE", "שלום", "cp1255"),
            ("RU", "Привет", "cp1251"), ("SR_CYRL", "Здраво", "cp1251"), ("PL", "Zażółć", "cp1250"),
            ("EL", "Γειά", "cp1253"), ("TR", "Günaydın", "cp1254"), ("FR", "Déjà vu", "cp1252"),
            ("BR_PT", "Não", "cp1252"), ("ZH", "你好", "gb18030"), ("ZH_BG", "你們好", "big5"),
            ("HU_EN", "Árvíztűrő", "cp1250"),
        ):
            with self.subTest(code=code):
                self.assertEqual(archive.as_utf8(text.encode(codec), code), b"\xef\xbb\xbf" + text.encode("utf-8"))

    def test_persian_gets_persian_yeh_and_keheh(self):
        self.assertEqual(archive.as_utf8("يك كتاب".encode("cp1256"), "FA"), "\ufeffیک کتاب".encode("utf-8"))

    def test_unknown_language_or_undecodable_bytes_are_left_alone(self):
        legacy = "بايد".encode("cp1256")
        self.assertEqual(archive.as_utf8(legacy, ""), legacy)
        self.assertEqual(archive.as_utf8(legacy, "HI"), legacy)
        self.assertEqual(archive.as_utf8(b"caf\xe9 \x81", "EN"), b"caf\xe9 \x81")

    def test_text_formats(self):
        self.assertTrue(archive.is_text(SubtitleFile("a.srt", SRT)))
        self.assertTrue(archive.is_text(SubtitleFile("a.ass", b"[Script Info]")))
        self.assertTrue(archive.is_text(SubtitleFile("a.sub", b"{10}{20}Hello")))
        self.assertFalse(archive.is_text(SubtitleFile("a.sub", b"{10}{20}Hello", idx=b"idx")))
        self.assertFalse(archive.is_text(SubtitleFile("a.sub", b"\x00\x00\x01\xba")))
        self.assertFalse(archive.is_text(SubtitleFile("a.sup", b"PG")))


class WriteTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.folder)

    def test_writes_the_file_and_its_idx(self):
        path = archive.write(SubtitleFile("Film.sub", b"sub", idx=b"idx"), self.folder)
        self.assertEqual(path, os.path.join(self.folder, "Film.sub"))
        with open(path, "rb") as handle:
            self.assertEqual(handle.read(), b"sub")
        with open(os.path.join(self.folder, "Film.idx"), "rb") as handle:
            self.assertEqual(handle.read(), b"idx")

    def test_legacy_persian_is_written_as_utf8(self):
        legacy = "1\r\n00:00:01,000 --> 00:00:02,000\r\nبايد از اينجا برويم.\r\n".encode("cp1256")
        path = archive.write(SubtitleFile("Film.fa.srt", legacy), self.folder, "FA")
        with open(path, "rb") as handle:
            text = handle.read().decode("utf-8-sig")
        self.assertEqual(text, "1\r\n00:00:01,000 --> 00:00:02,000\r\nباید از اینجا برویم.\r\n")

    def test_binary_subtitles_are_written_as_they_came(self):
        vobsub = SubtitleFile("Film.sub", b"\x00\x00\x01\xba\xe9", idx=b"idx")
        with open(archive.write(vobsub, self.folder, "FA"), "rb") as handle:
            self.assertEqual(handle.read(), b"\x00\x00\x01\xba\xe9")
        with open(archive.write(SubtitleFile("Film.sup", b"PG\xe9"), self.folder, "FA"), "rb") as handle:
            self.assertEqual(handle.read(), b"PG\xe9")

    def test_safe_name(self):
        self.assertEqual(archive.safe_name("../a/b/Film: Part 1?.SRT"), "Film_ Part 1.srt")
        self.assertEqual(archive.safe_name("a<b>|c.srt"), "a_b_c.srt")
        self.assertEqual(archive.safe_name("  ?.srt"), "subtitle.srt")
        self.assertEqual(archive.safe_name("فیلم.srt"), "فیلم.srt")


if __name__ == "__main__":
    unittest.main()
