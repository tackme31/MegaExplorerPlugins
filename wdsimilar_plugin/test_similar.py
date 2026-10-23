import unittest

from similar import SimilarityIndex, fingerprint, terms_of


class TermsOfTest(unittest.TestCase):
    def test_splits_wd_and_chara_tags_and_ignores_the_rest(self):
        tags = ["wd:1girl long_hair smile", "rating:general",
                "chara:hatsune_miku chara:kagamine_rin", "mytag"]
        self.assertEqual(tuple(terms_of(tags)), ("1girl", "long_hair", "smile",
                                                 "chara:hatsune_miku", "chara:kagamine_rin"))

    def test_keeps_order_and_drops_repeats_and_empty_words(self):
        self.assertEqual(tuple(terms_of(["wd:b  a b", "wd:", "chara:"])), ("b", "a"))

    def test_none_and_untagged(self):
        self.assertEqual(terms_of(None), {})
        self.assertEqual(terms_of(["holiday"]), {})

    def test_level_falls_from_100_to_50_within_each_tag(self):
        terms = terms_of(["wd:a b c", "chara:x chara:y", "wd:solo"])
        self.assertEqual(terms, {"a": 100, "b": 75, "c": 50,
                                 "chara:x": 100, "chara:y": 50, "solo": 100})


class RankTest(unittest.TestCase):
    def build(self, files):
        index = SimilarityIndex()
        for entry in files:
            handle, tags, *rest = entry
            index.add(handle, handle + ".jpg", "/" + handle + ".jpg", tags, *rest)
        return index

    def handles(self, ranking, count=100):
        return [m.handle for m in ranking.page(0, count)]

    def test_skips_files_without_wd_words(self):
        index = SimilarityIndex()
        self.assertFalse(index.add("a", "a.jpg", "/a.jpg", ["rating:general"]))
        self.assertEqual(len(index), 0)

    def test_identical_tags_score_one_and_the_query_is_excluded(self):
        index = self.build([("q", ["wd:1girl smile"]), ("a", ["wd:1girl smile"])])
        matches = index.rank(terms_of(["wd:1girl smile"]), exclude="q").page(0, 20)
        self.assertEqual([m.handle for m in matches], ["a"])
        self.assertAlmostEqual(matches[0].score, 1.0)

    def test_a_shared_rare_word_outranks_a_shared_common_one(self):
        # One word per tag, so every word sits first and position plays no part.
        index = self.build([
            ("q", ["wd:1girl", "wd:umbrella"]),
            ("common", ["wd:1girl", "wd:hat"]),
            ("rare", ["wd:umbrella", "wd:boy"]),
            ("x1", ["wd:1girl"]), ("x2", ["wd:1girl"]), ("x3", ["wd:1girl"]),
        ])
        matches = index.rank(terms_of(["wd:1girl", "wd:umbrella"]), exclude="q").page(0, 20)
        handles = [m.handle for m in matches]
        self.assertLess(handles.index("rare"), handles.index("common"))
        self.assertEqual(matches[handles.index("rare")].shared, ("umbrella",))

    def test_sharing_the_query_s_leading_word_counts_for_more(self):
        index = self.build([("q", ["wd:a b c"]), ("last", ["wd:c y"]), ("first", ["wd:a x"])])
        ranking = index.rank(terms_of(["wd:a b c"]), exclude="q")
        self.assertEqual(self.handles(ranking), ["first", "last"])

    def test_every_sharing_file_is_ranked_and_paged(self):
        files = [(f"f{i}", ["wd:cat"]) for i in range(5)] + [("dog", ["wd:dog"])]
        ranking = self.build(files).rank(terms_of(["wd:cat"]))
        self.assertEqual(len(ranking), 5)
        self.assertEqual(self.handles(ranking, 2), ["f0", "f1"])
        self.assertEqual([m.handle for m in ranking.page(4, 2)], ["f4"])
        self.assertEqual(ranking.page(5, 2), [])

    def test_unknown_query_words_give_nothing(self):
        index = self.build([("a", ["wd:cat"])])
        self.assertEqual(len(index.rank(terms_of(["wd:dog"]))), 0)

    def test_without_copies_drops_only_the_same_size_and_checksum(self):
        index = self.build([
            ("copy", ["wd:cat"], 100, "CRC", True),
            ("other_size", ["wd:cat"], 101, "CRC"),
            ("no_crc", ["wd:cat"], 100, None),
        ])
        ranking = index.rank(terms_of(["wd:cat"]))
        self.assertEqual(self.handles(ranking.without_copies(fingerprint(100, "CRC"))),
                         ["other_size", "no_crc"])
        self.assertIs(ranking.without_copies(fingerprint(100, None)), ranking)
        self.assertTrue(ranking.page(0, 1)[0].has_thumbnail)


if __name__ == "__main__":
    unittest.main()
