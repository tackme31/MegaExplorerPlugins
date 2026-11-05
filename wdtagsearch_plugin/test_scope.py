import json
import os
import tempfile
import unittest

from scope import SettingsError, describe, folders_to_list, load_folders, normalize, outermost


class Item:
    def __init__(self, handle, name):
        self.handle = handle
        self.name = name


class FakeContext:
    def __init__(self, tree):
        self.tree = tree  # handle -> [child Item]

    def children(self, folder, type=None, fields=None):
        return list(self.tree.get(folder.handle, []))


class LoadFoldersTest(unittest.TestCase):
    def load(self, text):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "settings.json")
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
            return load_folders(path)

    def test_missing_file_is_whole_drive(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertIsNone(load_folders(os.path.join(d, "settings.json")))

    def test_no_folders_is_whole_drive(self):
        self.assertIsNone(self.load("{}"))
        self.assertIsNone(self.load(json.dumps({"folders": []})))
        self.assertIsNone(self.load(json.dumps({"folders": ["  "]})))

    def test_folders_are_normalized_and_nested_ones_dropped(self):
        folders = ["Photos/", "/Photos/2024", "\\Illust\\2024", "/Illust/2024"]
        self.assertEqual(self.load(json.dumps({"folders": folders})), ["/Illust/2024", "/Photos"])

    def test_bad_settings_raise(self):
        for text in ("{", "[]", json.dumps({"folders": "/Photos"}), json.dumps({"folders": [1]})):
            with self.assertRaises(SettingsError):
                self.load(text)


class PathTest(unittest.TestCase):
    def test_normalize(self):
        self.assertEqual(normalize(" /a//b/ "), "/a/b")
        self.assertEqual(normalize("/"), "/")

    def test_outermost(self):
        self.assertEqual(outermost(["/ab", "/a", "/a/b"]), ["/a", "/ab"])
        self.assertEqual(outermost(["/a", "/"]), ["/"])


class FoldersToListTest(unittest.TestCase):
    def setUp(self):
        self.root = Item("r", "")
        self.ctx = FakeContext({
            "r": [Item("p", "Photos"), Item("p2", "Photos"), Item("i", "Illust")],
            "p": [Item("p24", "2024")],
            "p2": [Item("p224", "2024")],
        })

    def handles(self, paths):
        folders, missing = folders_to_list(self.ctx, self.root, paths)
        return [f.handle for f in folders], missing

    def test_whole_drive(self):
        self.assertEqual(self.handles(None), (["r"], []))

    def test_same_named_siblings_are_all_listed(self):
        self.assertEqual(self.handles(["/Photos/2024"]), (["p24", "p224"], []))

    def test_missing_folders_are_left_out(self):
        self.assertEqual(self.handles(["/Illust", "/Nope", "/Illust/x"]), (["i"], ["/Nope", "/Illust/x"]))

    def test_root(self):
        self.assertEqual(self.handles(["/"]), (["r"], []))


class DescribeTest(unittest.TestCase):
    def test_describe(self):
        self.assertEqual(describe(None, []), "")
        self.assertEqual(describe(["/a"], []), " Listed from 1 folder in settings.json.")
        self.assertEqual(describe(["/a", "/b"], ["/b"]), " Listed from 1 folder in settings.json. Not found: /b.")


if __name__ == "__main__":
    unittest.main()
