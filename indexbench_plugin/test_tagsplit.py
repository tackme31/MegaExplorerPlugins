import unittest

from tagsplit import CHARACTER, GENERAL, RATING, USER, split_tags


class SplitTagsTest(unittest.TestCase):
    def test_splits_each_kind(self):
        tags = ["wd:1girl long_hair smile", "rating:general",
                "chara:hatsune_miku chara:mari_(blue_archive)", "My Tag"]
        self.assertEqual(split_tags(tags), [
            (GENERAL, "1girl", 0), (GENERAL, "long_hair", 1), (GENERAL, "smile", 2),
            (RATING, "general", 0),
            (CHARACTER, "hatsune_miku", 0), (CHARACTER, "mari_(blue_archive)", 1),
            (USER, "my tag", 0),
        ])

    def test_drops_repeats_and_empty_words(self):
        self.assertEqual(split_tags(["wd:b  a B", "wd:", "chara:", "chara:x chara:"]),
                         [(GENERAL, "b", 0), (GENERAL, "a", 1), (CHARACTER, "x", 0)])

    def test_same_word_of_different_kinds_is_kept(self):
        self.assertEqual(split_tags(["wd:general", "rating:general"]),
                         [(GENERAL, "general", 0), (RATING, "general", 0)])

    def test_no_tags(self):
        self.assertEqual(split_tags(None), [])
        self.assertEqual(split_tags([]), [])


if __name__ == "__main__":
    unittest.main()
