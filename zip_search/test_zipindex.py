import io
import os
import random
import tempfile
import unittest
import zipfile

from zipindex import (BLOCK, READ_LIMIT, IndexCache, RemoteFile, clean_tags, display_name, extract, filter_terms,
                      format_size, has_extension, list_entries, matches, parse_extensions, safe_file_name,
                      tag_changes, tag_filter_terms, tags_match, unique_path)


def make_zip(files, compression=zipfile.ZIP_DEFLATED, comment=b""):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression) as archive:
        for name, data in files.items():
            if name.endswith("/"):
                archive.mkdir(name.rstrip("/"))
            else:
                archive.writestr(name, data)
        archive.comment = comment
    return buffer.getvalue()


class FakeMega:
    """items.readRange and items.fetchFile over bytes, counting the calls."""

    def __init__(self, data):
        self.data = data
        self.reads = []
        self.fetches = []
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)

    def read_range(self, offset, length):
        assert length <= READ_LIMIT, length
        self.reads.append((offset, length))
        return self.data[offset:offset + length]

    def fetch_range(self, offset, length):
        self.fetches.append((offset, length))
        path = os.path.join(self.tmp.name, f"{offset}-{length}.part")
        with open(path, "wb") as f:
            f.write(self.data[offset:offset + length])
        return path

    def remote(self):
        return RemoteFile(len(self.data), self.read_range, self.fetch_range)

    def __del__(self):
        self.tmp.cleanup()


class RemoteFileTest(unittest.TestCase):
    def test_reads_like_a_file(self):
        data = random.Random(1).randbytes(3 * READ_LIMIT + 5)
        mega = FakeMega(data)
        remote = mega.remote()
        remote.seek(10)
        self.assertEqual(remote.read(100), data[10:110])
        remote.seek(-50, 2)
        self.assertEqual(remote.read(), data[-50:])
        remote.seek(0)
        self.assertEqual(remote.read(), data)
        self.assertTrue(all(length <= READ_LIMIT for _, length in mega.reads))

    def test_small_reads_near_the_end_share_one_call(self):
        mega = FakeMega(bytes(5 * READ_LIMIT))
        remote = mega.remote()
        for offset in (-22, -20, -100, -40000):
            remote.seek(offset, 2)
            remote.read(10)
        self.assertEqual(len(mega.reads), 1)


class ListEntriesTest(unittest.TestCase):
    def test_lists_files_with_folder_and_name(self):
        data = make_zip({"top.txt": b"a", "dir/": b"", "dir/sub/deep.bin": b"x" * 1000})
        entries = list_entries(FakeMega(data).remote())
        self.assertEqual([(e.path, e.name, e.size) for e in entries],
                         [("", "top.txt", 1), ("dir/sub", "deep.bin", 1000)])

    def test_a_small_zip_takes_one_call(self):
        mega = FakeMega(make_zip({f"f{i}.txt": b"hello" for i in range(50)}))
        list_entries(mega.remote())
        self.assertEqual(len(mega.reads), 1)

    def test_a_long_comment_and_a_large_index(self):
        files = {f"folder{i % 7}/file-{i:05}.txt": b"" for i in range(20000)}
        mega = FakeMega(make_zip(files, zipfile.ZIP_STORED, comment=b"c" * 65000))
        entries = list_entries(mega.remote())
        self.assertEqual(len(entries), 20000)
        self.assertEqual(entries[-1].name, "file-19999.txt")

    def test_not_a_zip(self):
        with self.assertRaises(zipfile.BadZipFile):
            list_entries(FakeMega(b"not a zip at all" * 10).remote())


class DisplayNameTest(unittest.TestCase):
    def flagless(self, raw):
        # zipfile sets the UTF-8 flag for any non-ASCII name, so write an ASCII name of the
        # same length and patch the bytes in, as an older Japanese tool would have written it.
        placeholder = b"x" * len(raw)
        data = make_zip({placeholder.decode(): b"content"}).replace(placeholder, raw)
        info = zipfile.ZipFile(io.BytesIO(data)).infolist()[0]
        self.assertFalse(info.flag_bits & 0x800)
        return info, data

    def test_cp932_name_without_the_utf8_flag(self):
        info, _ = self.flagless("写真/あ.txt".encode("cp932"))
        self.assertEqual(display_name(info), "写真/あ.txt")

    def test_utf8_name_without_the_flag(self):
        info, _ = self.flagless("写真/あ.txt".encode("utf-8"))
        self.assertEqual(display_name(info), "写真/あ.txt")

    def test_utf8_name_with_the_flag(self):
        data = make_zip({"日本語.txt": b""})
        info = zipfile.ZipFile(io.BytesIO(data)).infolist()[0]
        self.assertEqual(display_name(info), "日本語.txt")

    def test_a_cp932_entry_still_extracts(self):
        info, data = self.flagless("あ.txt".encode("cp932"))
        out = io.BytesIO()
        self.assertTrue(extract(FakeMega(data).remote(), info.header_offset, out))
        self.assertEqual(out.getvalue(), b"content")


class ExtractTest(unittest.TestCase):
    def extract_named(self, mega, name):
        entry = next(e for e in list_entries(mega.remote()) if e.name == name)
        mega.reads.clear()
        out = io.BytesIO()
        with mega.remote() as remote:
            self.assertTrue(extract(remote, entry.offset, out))
        return out.getvalue()

    def test_stored_and_deflated(self):
        payload = b"hello world " * 1000
        for method in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED, zipfile.ZIP_BZIP2, zipfile.ZIP_LZMA):
            mega = FakeMega(make_zip({"a.txt": b"other", "b/c.txt": payload}, method))
            self.assertEqual(self.extract_named(mega, "c.txt"), payload, method)

    def test_a_large_entry_comes_in_one_fetch(self):
        payload = random.Random(2).randbytes(3 * READ_LIMIT)
        mega = FakeMega(make_zip({"pad.bin": bytes(2 * READ_LIMIT), "big.bin": payload, "z.txt": b"z"},
                                 zipfile.ZIP_STORED))
        self.assertEqual(self.extract_named(mega, "big.bin"), payload)
        self.assertEqual(len(mega.fetches), 1)
        self.assertLessEqual(len(mega.reads), 3)

    def test_a_small_entry_reads_little(self):
        mega = FakeMega(make_zip({"pad.bin": bytes(4 * READ_LIMIT), "small.txt": b"s" * 100,
                                  "end.bin": bytes(4 * READ_LIMIT)}, zipfile.ZIP_STORED))
        self.assertEqual(self.extract_named(mega, "small.txt"), b"s" * 100)
        self.assertEqual(mega.fetches, [])
        self.assertLessEqual(sum(length for _, length in mega.reads), BLOCK + (128 << 10))

    def test_cancel_stops_writing(self):
        mega = FakeMega(make_zip({"big.bin": bytes(3 * READ_LIMIT)}, zipfile.ZIP_STORED))
        entry = list_entries(mega.remote())[0]
        with mega.remote() as remote:
            self.assertFalse(extract(remote, entry.offset, io.BytesIO(), lambda: True))


class IndexCacheTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "cache.json")
        self.entries = list_entries(FakeMega(make_zip({"a.txt": b"a", "dir/b.txt": b"bb"})).remote())

    def tearDown(self):
        self.tmp.cleanup()

    def test_kept_across_saves_while_mtime_and_size_match(self):
        cache = IndexCache(self.path)
        cache.put("h1", 100, 2000, self.entries)
        cache.save()
        again = IndexCache(self.path)
        self.assertEqual(again.get("h1", 100, 2000), self.entries)
        self.assertIsNone(again.get("h1", 101, 2000))
        self.assertIsNone(again.get("h1", 100, 2001))
        self.assertIsNone(again.get("h2", 100, 2000))

    def test_cached_entries_still_extract(self):
        data = make_zip({"a.txt": b"first", "b.txt": b"second"})
        cache = IndexCache(self.path)
        cache.put("h", 1, len(data), list_entries(FakeMega(data).remote()))
        cache.save()
        entry = IndexCache(self.path).get("h", 1, len(data))[1]
        out = io.BytesIO()
        self.assertTrue(extract(FakeMega(data).remote(), entry.offset, out))
        self.assertEqual(out.getvalue(), b"second")

    def test_an_unknown_mtime_is_never_cached(self):
        cache = IndexCache(self.path)
        cache.put("h", None, 10, self.entries)
        self.assertIsNone(cache.get("h", None, 10))

    def test_two_windows_keep_each_other_s_indexes(self):
        first, second = IndexCache(self.path), IndexCache(self.path)
        first.put("h1", 1, 1, self.entries)
        second.put("h2", 2, 2, self.entries)
        first.save()
        second.save()
        both = IndexCache(self.path)
        self.assertIsNotNone(both.get("h1", 1, 1))
        self.assertIsNotNone(both.get("h2", 2, 2))

    def test_a_damaged_file_is_an_empty_cache(self):
        for content in ("{not json", "[]", '{"version": 99, "zips": {}}'):
            with open(self.path, "w", encoding="utf-8") as f:
                f.write(content)
            self.assertIsNone(IndexCache(self.path).get("h", 1, 1))

    def test_clear(self):
        cache = IndexCache(self.path)
        cache.put("h1", 1, 1, self.entries)
        cache.put("h2", 2, 2, self.entries)
        cache.save()
        self.assertEqual(IndexCache(self.path).clear(), 2)
        self.assertFalse(os.path.exists(self.path))
        self.assertIsNone(IndexCache(self.path).get("h1", 1, 1))
        self.assertEqual(IndexCache(self.path).clear(), 0)


class HelpersTest(unittest.TestCase):
    def test_filter(self):
        terms = filter_terms("  IMG  .jpg ")
        self.assertTrue(matches("img_0001.JPG", terms))
        self.assertFalse(matches("img_0001.png", terms))
        self.assertTrue(matches("anything", filter_terms("")))

    def test_safe_file_name(self):
        self.assertEqual(safe_file_name('a:b*?.txt'), "a_b__.txt")
        self.assertEqual(safe_file_name("CON.txt"), "_CON.txt")
        self.assertEqual(safe_file_name("name. "), "name")

    def test_unique_path(self):
        taken = {os.path.join("d", "a.txt"), os.path.join("d", "a (1).txt")}
        self.assertEqual(unique_path("d", "a.txt", taken.__contains__), os.path.join("d", "a (2).txt"))
        self.assertEqual(unique_path("d", "b.txt", taken.__contains__), os.path.join("d", "b.txt"))

    def test_format_size(self):
        self.assertEqual(format_size(512), "512 B")
        self.assertEqual(format_size(1536), "1.5 KB")


class ExtensionsTest(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(parse_extensions(" zip, .CBZ ,*.epub,, zip"), [".zip", ".cbz", ".epub"])
        with self.assertRaises(ValueError):
            parse_extensions(" , . ")

    def test_match(self):
        extensions = parse_extensions("zip, cbz")
        self.assertTrue(has_extension("Comic.CBZ", extensions))
        self.assertFalse(has_extension("notzip", extensions))
        self.assertFalse(has_extension("a.zip.txt", extensions))


class TagsTest(unittest.TestCase):
    def test_filter(self):
        terms = tag_filter_terms(" Photo , 2024 ,, ")
        self.assertEqual(terms, ["photo", "2024"])
        self.assertTrue(tags_match(["photos", "trip 2024"], terms))
        self.assertFalse(tags_match(["photos"], terms))
        self.assertTrue(tags_match([], []))
        self.assertFalse(tags_match([], ["x"]))

    def test_clean(self):
        self.assertEqual(clean_tags([" a ", "", "B", "b", "a b"]), ["a", "B", "a b"])
        with self.assertRaises(ValueError):
            clean_tags(["a,b"])
        with self.assertRaises(ValueError):
            clean_tags([str(i) for i in range(11)])
        with self.assertRaises(ValueError):
            clean_tags(["x" * 1600, "y" * 1600])

    def test_changes(self):
        self.assertEqual(tag_changes(["a", "B", "c"], ["b", "c", "d"]), (["d"], ["a"]))
        self.assertEqual(tag_changes([], ["x"]), (["x"], []))


if __name__ == "__main__":
    unittest.main()
