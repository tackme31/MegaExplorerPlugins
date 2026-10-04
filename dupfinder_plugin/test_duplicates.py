import unittest

from duplicates import DuplicateFinder
from megaexplorer_plugin import Item


def item(handle, path, size, crc):
    return Item({"handle": handle, "path": path, "size": size, "crc": crc})


class DuplicateFinderTest(unittest.TestCase):
    def find(self, *items):
        finder = DuplicateFinder()
        for i in items:
            finder.add(i)
        return finder

    def test_groups_need_both_size_and_crc_to_match(self):
        finder = self.find(
            item("a", "/a.jpg", 100, "X"),
            item("b", "/b.jpg", 100, "X"),
            item("c", "/c.jpg", 200, "X"),
            item("d", "/d.jpg", 100, "Y"),
        )
        groups = finder.groups()
        self.assertEqual(len(groups), 1)
        self.assertEqual([f.handle for f in groups[0].files], ["a", "b"])

    def test_largest_waste_comes_first(self):
        finder = self.find(
            item("a", "/a", 10, "S"), item("b", "/b", 10, "S"), item("c", "/c", 10, "S"),
            item("d", "/d", 100, "L"), item("e", "/e", 100, "L"),
        )
        self.assertEqual([g.wasted for g in finder.groups()], [100, 20])

    def test_empty_and_unfingerprinted_files_are_counted_not_grouped(self):
        finder = self.find(
            item("a", "/a", 0, "Z"), item("b", "/b", 0, "Z"),
            item("c", "/c", 5, None), item("d", "/d", 5, None),
        )
        self.assertEqual(finder.groups(), [])
        self.assertEqual((finder.files, finder.empty, finder.no_crc), (4, 2, 2))

    def test_a_file_listed_twice_is_one_file(self):
        finder = self.find(item("a", "/a", 10, "S"), item("a", "/a", 10, "S"))
        self.assertEqual(finder.groups(), [])
        self.assertEqual(finder.files, 1)


if __name__ == "__main__":
    unittest.main()
