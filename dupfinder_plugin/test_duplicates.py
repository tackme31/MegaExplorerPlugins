import unittest

from duplicates import DuplicateFinder, Group, format_size, parent_path
from megaexplorer_plugin import Item


def item(handle, path, size, crc):
    return Item({"handle": handle, "name": path.rsplit("/", 1)[1], "path": path, "size": size, "crc": crc})


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


class GroupTitleTest(unittest.TestCase):
    def test_one_name_is_the_title(self):
        group = Group(1, [item("a", "/x/a.jpg", 1, "C"), item("b", "/y/a.jpg", 1, "C")])
        self.assertEqual(group.title, "a.jpg")

    def test_other_names_are_counted(self):
        group = Group(1, [item("a", "/a.jpg", 1, "C"), item("b", "/b.jpg", 1, "C"),
                          item("c", "/c.jpg", 1, "C"), item("d", "/z/a.jpg", 1, "C")])
        self.assertEqual(group.title, "a.jpg (+2 other names)")


class FormattingTest(unittest.TestCase):
    def test_parent_path(self):
        self.assertEqual(parent_path("/Photos/2024/a.jpg"), "/Photos/2024")
        self.assertEqual(parent_path("/a.jpg"), "/")

    def test_format_size(self):
        self.assertEqual(format_size(0), "0 B")
        self.assertEqual(format_size(1023), "1023 B")
        self.assertEqual(format_size(1536), "1.5 KB")
        self.assertEqual(format_size(3 * 1024 ** 3), "3.0 GB")
        self.assertEqual(format_size(2048 * 1024 ** 4), "2048.0 TB")


if __name__ == "__main__":
    unittest.main()
